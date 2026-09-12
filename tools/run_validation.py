#!/usr/bin/env python3
"""Run current Go checks and explicitly report missing full-product coverage."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from test_catalog import catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go', default='go')
    parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--fuzz-seconds', type=int, default=10)
    args = parser.parse_args()
    if args.fuzz_seconds < 1:
        parser.error('--fuzz-seconds must be positive')
    root = Path(__file__).resolve().parents[1]
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = root / 'test-results' / run_id
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, GOTOOLCHAIN='local', GOCACHE=str(root/'.cache/build'))
    checks = []

    def run(name, argv, timeout=180):
        print(f'Running {name}', flush=True)
        start = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=root, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=timeout)
            log, code = result.stdout, result.returncode
        except subprocess.TimeoutExpired as exc:
            log, code = (exc.stdout or b'') + b'\nTIMEOUT\n', 124
        except OSError as exc:
            log, code = str(exc).encode(), 127
        (output / f'{name}.log').write_bytes(log)
        checks.append({'name': name, 'argv': argv, 'exit_code': code,
                       'status': 'passed' if code == 0 else 'failed',
                       'seconds': round(time.monotonic()-start, 3),
                       'log': f'{name}.log'})
        print(f'{name}: {checks[-1]["status"]}', flush=True)
        return code == 0

    run('toolchain', [args.go, 'version'])
    run('unit-race-coverage', [args.go, 'test', '-count=1', '-race', '-covermode=atomic',
                              f'-coverprofile={output / "coverage.out"}', '-json', './...'])
    if (output/'coverage.out').exists():
        run('coverage-functions', [args.go, 'tool', 'cover', '-func', str(output/'coverage.out')])
    run('vet', [args.go, 'vet', './...'])
    for package, target in [('serial', 'FuzzCompare'), ('ttl', 'FuzzRoundTrip'), ('ttl', 'FuzzParse')]:
        run(f'fuzz-{target}', [args.go, 'test', f'./internal/{package}', '-run', '^$',
                              '-fuzz', target, '-fuzztime', f'{args.fuzz_seconds}s', '-parallel', '2'])
    inventory = catalog(root/'upstream/bind-9.20.27')
    saved = root/'docs/full-test-catalog.json'
    if saved.exists():
        previous = json.loads(saved.read_text())
        if previous.get('baseline') == inventory['baseline']:
            previous_suites = {s['suite']:s for s in previous.get('suites',[])}
            for suite in inventory['suites']:
                prior = previous_suites.get(suite['suite'],{})
                for key in ['upstream_status','upstream_counts']:
                    if key in prior:
                        suite[key] = prior[key]
    (root/'docs/full-test-catalog.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n')
    sources = {}
    for base, pattern in [('internal', '*.go'), ('tools', '*.py')]:
        for path in sorted((root/base).rglob(pattern)):
            sources[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {'run_id': run_id, 'baseline': 'BIND 9.20.27', 'checks': checks,
              'go_checks_passed': all(c['status']=='passed' for c in checks),
              'go_system_suites_passed': 0, 'go_system_suites_blocked': inventory['suite_count'],
              'release_ready': False,
              'blocking_reasons': ['DNS server and CLI features are not implemented',
                                   'All upstream service-level tests remain unexecuted against Go'],
              'source_sha256': sources,
              'scope_note': 'Local synthetic and upstream fixtures; no real user production data used'}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines = ['# 当前全功能测试报告', '', f'运行标识（UTC）：{run_id}', '',
             '**全功能验收未通过。已实现模块检查结果如下；174 个系统测试套件因服务功能未实现而阻塞。**', '',
             '| 已执行检查 | 结果 | 日志 |', '|---|---|---|']
    lines += [f"| {c['name']} | {c['status']} | [{c['name']}.log]({run_id}/{c['name']}.log) |" for c in checks]
    lines += ['', '| 用户场景分组 | 阻塞的系统测试套件数 |', '|---|---|']
    lines += [f'| {name} | {count} |' for name,count in sorted(Counter(s['scenario'] for s in inventory['suites']).items())]
    lines += ['', '套件数不等于运行时测试用例数；参数化、跳过条件及环境依赖由 pytest 在实际运行时决定。',
              '本次未使用真实用户数据，未对用户生产 DNS 发起测试。',
              '上游 C 基准环境的构建情况另见 docs/full-testing.md。',
              '短时模糊测试、语句覆盖率和差分样本通过均不能证明整个 BIND 已兼容。', '',
              f'[机器可读报告]({run_id}/report.json)', '']
    (root/'test-results/latest.md').write_text('\n'.join(lines))
    print(f'Report: {output}/report.json', flush=True)
    print(f'Full product gate: BLOCKED ({inventory["suite_count"]} unimplemented system suites)', flush=True)
    return 1 if not report['go_checks_passed'] else (2 if args.require_complete else 0)


if __name__ == '__main__':
    raise SystemExit(main())

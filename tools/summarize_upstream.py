#!/usr/bin/env python3
"""Summarize completed upstream JUnit runs, preserving skips and rerun history."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from test_catalog import catalog

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('runs', nargs='+', type=Path, help='Oldest to newest completed result directories')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
effective, history = {}, []
for directory in args.runs:
    junit = directory/'upstream-system.xml'
    if not junit.exists():
        parser.error(f'No completed JUnit report: {junit}')
    cases = []
    for case in ET.parse(junit).iter('testcase'):
        state, reason = 'passed', ''
        for tag, status in [('error','error'),('failure','failed'),('skipped','skipped')]:
            node = case.find(tag)
            if node is not None:
                state, reason = status, node.get('message') or (node.text or '')
                break
        key = (case.get('classname',''),case.get('name',''))
        item = {'classname':key[0], 'name':key[1], 'status':state, 'reason':reason,
                'run':str(directory.relative_to(root)) if directory.is_relative_to(root) else str(directory)}
        effective[key] = item
        cases.append(item)
    history.append({'run':str(directory),'counts':dict(Counter(c['status'] for c in cases))})
counts = Counter(c['status'] for c in effective.values())
unit = {}
for directory in args.runs:
    log = directory/'upstream-unit.log'
    if log.exists():
        unit = {name.lower():sum(map(int,re.findall(r'^# '+name+r':\s+(\d+)',log.read_text(),re.MULTILINE)))
                for name in ['TOTAL','PASS','SKIP','FAIL','ERROR','XFAIL','XPASS']}
inventory = catalog(root/'upstream/bind-9.20.27')
by_suite = {}
for suite in inventory['suites']:
    matches = [c for c in effective.values() if c['classname'].split('.')[0] == suite['suite']]
    suite_counts = dict(Counter(c['status'] for c in matches))
    state = 'not_collected'
    if matches:
        state = 'failed' if any(c['status'] in ['failed','error'] for c in matches) else (
            'partial_skipped' if any(c['status']=='skipped' for c in matches) else 'passed')
    suite['upstream_status'] = state
    suite['upstream_counts'] = suite_counts
    by_suite[suite['suite']] = {'status':state,'counts':suite_counts}
(root/'docs/full-test-catalog.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n')
report = {'subject':'upstream C BIND 9.20.27, not Go', 'effective_counts':dict(counts),
          'unit_test_programs':unit,'history':history,'suites':by_suite,
          'unresolved':[c for c in effective.values() if c['status']!='passed'],
          'go_full_feature_gate':'blocked_unimplemented'}
(root/'test-results/upstream-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
lines = ['# BIND 原版全量测试结果', '', '**被测对象为原版 C BIND 9.20.27；Go 全功能测试仍因服务未实现而阻塞。**', '',
         f"原版单元测试程序：{unit.get('total',0)}；通过：{unit.get('pass',0)}；失败：{unit.get('fail',0)}；错误：{unit.get('error',0)}。", '',
         f"合并补测后的系统用例：{len(effective)}；通过：{counts['passed']}；失败：{counts['failed']}；错误：{counts['error']}；跳过：{counts['skipped']}。", '',
         '合并以 pytest classname/name 标识为准，后一次结果替代前一次状态；原始运行历史保留在 JSON 中。', '',
         '| 未通过的用例 | 状态 | 原因 |','|---|---|---|']
for case in report['unresolved']:
    reason = case['reason'].replace('\n',' ').replace('|','\\|')
    lines.append(f"| {case['classname']}::{case['name']} | {case['status']} | {reason} |")
lines += ['', '[完整机器报告](upstream-summary.json)', '']
(root/'test-results/upstream-summary.md').write_text('\n'.join(lines))
print(json.dumps({'unit':unit,'system':dict(counts),'suites':dict(Counter(s['status'] for s in by_suite.values()))},indent=2))

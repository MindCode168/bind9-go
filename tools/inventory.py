#!/usr/bin/env python3
"""Inventory a local, extracted BIND source release without executing its code."""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def inventory(root):
    files = sorted(p for p in root.rglob('*') if p.is_file() and not p.is_symlink())
    by_component = collections.defaultdict(lambda: {'files': 0, 'lines': 0})
    source_files = []
    for path in files:
        relative = path.relative_to(root)
        if path.suffix not in {'.c', '.h'}:
            continue
        component = '/'.join(relative.parts[:2]) if len(relative.parts) > 2 else relative.parts[0]
        data = path.read_bytes()
        lines = len(data.splitlines())
        by_component[component]['files'] += 1
        by_component[component]['lines'] += lines
        source_files.append({'path': relative.as_posix(), 'lines': lines,
                             'sha256': hashlib.sha256(data).hexdigest(), 'status': 'unported'})
    system = root / 'bin/tests/system'
    suites = sorted(p.name for p in system.iterdir() if p.is_dir()) if system.exists() else []
    return {'source_directory': root.name, 'total_files': len(files),
            'c_header_files': len(source_files),
            'c_header_lines': sum(x['lines'] for x in source_files),
            'components': dict(sorted(by_component.items())),
            'system_test_directories': suites, 'source_files': source_files}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if not (args.source / 'lib/dns').is_dir():
        parser.error('source must be an extracted BIND tree containing lib/dns')
    data = inventory(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in data.items() if k != 'source_files'}, indent=2))

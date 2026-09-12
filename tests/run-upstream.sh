#!/usr/bin/env bash
# Run only inside the disposable test container, with /results mounted separately.
set -euo pipefail
cd /src
mkdir -p /results
chown tester:tester /results
bin/named/named -V > /results/named-version.txt 2>&1
cp config.log /results/config.log
dpkg-query -W > /results/packages.txt
python3 -m pip freeze > /results/python-packages.txt
cd /src/bin/tests/system
sh ifconfig.sh up > /results/network-setup.log 2>&1
trap 'sh /src/bin/tests/system/ifconfig.sh down >/dev/null 2>&1 || true' EXIT
ip address show dev lo > /results/test-addresses.txt
set +e
gosu tester make -C /src/tests -j4 check > /results/upstream-unit.log 2>&1
unit_status=$?
gosu tester timeout 1800 python3 -m pytest -n 4 --noclean \
    --junitxml=/results/upstream-system.xml > /results/upstream-system.log 2>&1
system_status=$?
set -e
python3 - "$unit_status" "$system_status" <<'PY'
import json
from pathlib import Path
import sys
import tarfile
import xml.etree.ElementTree as ET

output = Path('/results')
summary = {'subject':'upstream C BIND 9.20.27; not the Go port',
           'unit_exit_code':int(sys.argv[1]), 'system_exit_code':int(sys.argv[2]),
           'counts':{'passed':0,'failed':0,'error':0,'skipped':0},'testcases':[]}
junit = output/'upstream-system.xml'
if junit.exists():
    for case in ET.parse(junit).iter('testcase'):
        state = next((s for s in ['failure','error','skipped'] if case.find(s) is not None), 'passed')
        state = 'failed' if state == 'failure' else state
        summary['counts'][state] += 1
        summary['testcases'].append({'classname':case.get('classname'),'name':case.get('name'),'status':state})
else:
    summary['junit_missing'] = True
summary['all_selected_tests_passed'] = (
    summary['unit_exit_code']==0 and summary['system_exit_code']==0
    and bool(summary['testcases']) and summary['counts']['skipped']==0
    and summary['counts']['failed']==0 and summary['counts']['error']==0)
with tarfile.open(output/'upstream-logs.tar.gz','w:gz') as archive:
    for p in Path('/src').rglob('*'):
        if p.is_file() and not p.is_symlink() and (p.name.endswith(('.log','.log.txt')) or p.name.startswith('named.run') or '.err.' in p.name or '.out.' in p.name):
            archive.add(p,arcname=p.relative_to('/src'))
(output/'upstream-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='testcases'},indent=2))
PY
if [ "$unit_status" -ne 0 ] || [ "$system_status" -ne 0 ]; then
    exit 1
fi

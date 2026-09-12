#!/usr/bin/env bash
set -euo pipefail
mkdir -p /results
chown tester:tester /results
cd /src/bin/tests/system
sh ifconfig.sh up > /results/network-setup.log 2>&1
trap 'sh /src/bin/tests/system/ifconfig.sh down >/dev/null 2>&1 || true' EXIT
python3 -m pip freeze > /results/python-packages.txt
dpkg-query -W > /results/packages.txt
set +e
gosu tester timeout 1800 python3 -m pytest -n 2 --noclean \
    --junitxml=/results/upstream-system.xml "$@" > /results/upstream-system.log 2>&1
status=$?
set -e
python3 - "$status" <<'PY'
import json
from pathlib import Path
import sys
import tarfile
with tarfile.open('/results/upstream-logs.tar.gz','w:gz') as archive:
    for p in Path('/src/bin/tests/system').rglob('*'):
        if p.is_file() and not p.is_symlink() and (p.name.endswith(('.log','.log.txt')) or p.name.startswith('named.run') or '.err.' in p.name or '.out.' in p.name):
            archive.add(p,arcname=p.relative_to('/src'))
Path('/results/exit-status.json').write_text(json.dumps({'exit_code':int(sys.argv[1])})+'\n')
PY
exit "$status"

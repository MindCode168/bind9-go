#!/usr/bin/env python3
"""Build serial fixtures by executing the pinned upstream C implementation.

Only its project-header include is removed; comparison function bodies remain
unchanged. This is an isolated arithmetic oracle, not a build of named.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
source = args.source / 'lib/isc/serial.c'
original = source.read_text()
assert original.count('#include <isc/serial.h>') == 1
driver = r'''
#include <stdio.h>
static void emit(uint32_t a, uint32_t b) {
    printf("%u %u %d %d %d %d %d %d\n", a, b,
      isc_serial_lt(a,b), isc_serial_gt(a,b), isc_serial_le(a,b),
      isc_serial_ge(a,b), isc_serial_eq(a,b), isc_serial_ne(a,b));
}
int main(void) {
    uint32_t edges[] = {0,1,2,0x7ffffffeU,0x7fffffffU,0x80000000U,
                       0x80000001U,0xfffffffeU,0xffffffffU};
    for (unsigned i=0; i<9; i++)
      for (unsigned j=0; j<9; j++) emit(edges[i],edges[j]);
    uint32_t state=0x12345678U;
    for (unsigned i=0; i<4096; i++) {
      state=state*1664525U+1013904223U;
      uint32_t a=state;
      state=state*1664525U+1013904223U;
      emit(a,state);
      emit(a,a^0x80000000U);
    }
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='bind-serial-') as temp:
    cfile = Path(temp) / 'oracle.c'
    binary = Path(temp) / 'oracle'
    cfile.write_text(original.replace('#include <isc/serial.h>', '') + driver)
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    str(cfile), '-o', str(binary)], check=True)
    output = subprocess.check_output([str(binary)])
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_bytes(output)
args.output.with_suffix('.json').write_text(json.dumps({
    'upstream': args.source.name, 'source': 'lib/isc/serial.c',
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'fixture_sha256': hashlib.sha256(output).hexdigest(),
    'cases': len(output.splitlines()),
    'columns': ['a', 'b', 'lt', 'gt', 'le', 'ge', 'eq', 'ne'],
    'method': 'clang; upstream function bodies unchanged; project header omitted'
}, indent=2) + '\n')
print(f'Wrote {len(output.splitlines())} upstream comparison cases')

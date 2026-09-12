#!/usr/bin/env python3
"""Verify saved C/Go fixture expectations against full compiled BIND libraries.

Run in the upstream test image with this project mounted read-only at /port.
"""
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess

port = Path('/port')
library = Path('/tmp/compiled-oracle.so')
subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                '-I/src', '-I/src/lib/isc/include', '-I/src/lib/dns/include',
                '-I/src/lib/isc', str(port/'tests/compiled-oracle.c'),
                '-L/src/lib/dns/.libs', '-L/src/lib/isc/.libs',
                '-Wl,-rpath,/src/lib/dns/.libs', '-Wl,-rpath,/src/lib/isc/.libs',
                '-ldns', '-lisc', '-o', str(library)], check=True)
lib = ctypes.CDLL(str(library))
lib.bind_go_parse.argtypes = [ctypes.c_char_p,ctypes.c_uint,ctypes.c_int,ctypes.POINTER(ctypes.c_uint32)]
lib.bind_go_parse.restype = ctypes.c_int
lib.bind_go_format.argtypes = [ctypes.c_uint32,ctypes.c_int,ctypes.c_int,ctypes.c_char_p]
lib.bind_go_format.restype = ctypes.c_int
fixture = port/'internal/ttl/testdata/upstream.json'
data = json.loads(fixture.read_text())
results = {0:'success',1:'range',2:'syntax',3:'badttl'}
for case in data['parse']:
    text = bytes.fromhex(case['hex'])
    value = ctypes.c_uint32(0)
    result = lib.bind_go_parse(text,len(text),case['counter'],ctypes.byref(value))
    assert results.get(result) == case['result'], case
    if result == 0:
        assert value.value == case['value'], case
for case in data['format']:
    output = ctypes.create_string_buffer(256)
    result = lib.bind_go_format(case['value'],case['verbose'],case['upcase'],output)
    assert result == 0 and output.value.decode() == case['text'], case
isc = ctypes.CDLL('/src/lib/isc/.libs/libisc.so')
operations = [getattr(isc,'isc_serial_'+name) for name in ['lt','gt','le','ge','eq','ne']]
for operation in operations:
    operation.argtypes = [ctypes.c_uint32,ctypes.c_uint32]
    operation.restype = ctypes.c_bool
serial = port/'internal/serial/testdata/upstream.txt'
serial_count = 0
for line in serial.read_text().splitlines():
    a,b,*expected = map(int,line.split())
    assert [int(op(a,b)) for op in operations] == expected, (a,b)
    serial_count += 1
print(json.dumps({'subject':'full compiled BIND 9.20.27 libdns/libisc', 'status':'passed',
                  'serial_input_pairs':serial_count, 'ttl_parse_cases':len(data['parse']),
                  'ttl_format_cases':len(data['format']),
                  'fixture_sha256':{str(p.relative_to(port)):hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in [fixture,serial]}},indent=2))

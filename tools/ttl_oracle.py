#!/usr/bin/env python3
"""Generate differential fixtures from unmodified BIND TTL/parseint functions.

ISC result constants and buffer helpers are supplied by a minimal test shim.
This checks text parsing and formatting, not a complete libdns build or ABI.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import tempfile

SHIM = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stddef.h>
typedef int isc_result_t;
enum { ISC_R_SUCCESS=0, ISC_R_RANGE=1, DNS_R_SYNTAX=2,
       DNS_R_BADTTL=3, ISC_R_BADNUMBER=4, ISC_R_NOSPACE=5 };
typedef struct { char *base; unsigned int length; } isc_textregion_t;
typedef struct { unsigned char *base; unsigned int length; } isc_region_t;
typedef struct { unsigned char *base; unsigned int length, used; } isc_buffer_t;
#define INSIST(x) assert(x)
#define POST(x) ((void)(x))
#define RETERR(x) do { int ret_ = (x); if (ret_ != 0) return ret_; } while (0)
static unsigned char isc_ascii_toupper(unsigned char c) {
  return c >= 'a' && c <= 'z' ? c - 'a' + 'A' : c;
}
static void isc_buffer_availableregion(isc_buffer_t *b, isc_region_t *r) {
  r->base=b->base+b->used; r->length=b->length-b->used;
}
static void isc_buffer_usedregion(isc_buffer_t *b, isc_region_t *r) {
  r->base=b->base; r->length=b->used;
}
static void isc_buffer_add(isc_buffer_t *b, unsigned int n) {
  assert(n<=b->length-b->used); b->used+=n;
}
'''
WRAPPERS = r'''
int oracle_parse(char *text, unsigned int length, int counter, uint32_t *value) {
  isc_textregion_t r={text,length};
  return counter ? dns_counter_fromtext(&r,value) : dns_ttl_fromtext(&r,value);
}
int oracle_format(uint32_t value, int verbose, int upcase, char *output) {
  isc_buffer_t b={(unsigned char *)output,255,0};
  int result=dns_ttl_totext(value,verbose,upcase,&b);
  output[b.used]='\0'; return result;
}
'''
RESULTS = {0: 'success', 1: 'range', 2: 'syntax', 3: 'badttl', 4: 'badnumber', 5: 'nospace'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    paths = ['lib/isc/parseint.c', 'lib/dns/ttl.c']
    sources = [(args.source / p).read_text() for p in paths]
    # Only remove project header includes; preserve upstream function bodies.
    source = SHIM + '\n'.join(re.sub(r'^#include <(?:isc|dns)/[^>]+>\n', '', s,
                                     flags=re.MULTILINE) for s in sources) + WRAPPERS
    rng = random.Random(92027)
    inputs = {b'', b'0', b'1\0trailing', b'\0', b'1h5', b'0h5', b'0h0m5',
              b'1H2m3S', b'-1', b'+1', b' 1', b'1 ', b'1h1h', b'1s1w',
              b'4294967295', b'4294967296', b'4294967295s1s', b'4294967295w'}
    for n in [0, 1, 59, 60, 3600, 0x7fffffff, 0xffffffff, 0x100000000]:
        for suffix in ['', 's', 'S', 'm', 'h', 'd', 'w', 'x', 's1s', '\0junk']:
            inputs.add((str(n) + suffix).encode())
    for length in [0, 1, 62, 63, 64, 65, 100]:
        inputs.add(b'0' * length)
        inputs.add(b'9' * length)
        inputs.add(b'1\0' + b'x' * length)
    for _ in range(5000):
        inputs.add(''.join(str(rng.randrange(0, 100000)) + rng.choice('wWdDhHmMsS')
                           for _ in range(rng.randrange(1, 6))).encode())
    alphabet = b'0123456789wWdDhHmMsS+- .\x00\xff\x80\t\n'
    for _ in range(5000):
        inputs.add(bytes(rng.choice(alphabet) for _ in range(rng.randrange(0, 80))))
    values = {0, 1, 59, 60, 61, 3599, 3600, 86400, 604800, 788645, 0x7fffffff, 0xffffffff}
    values.update(rng.randrange(0x100000000) for _ in range(2048))
    with tempfile.TemporaryDirectory(prefix='bind-ttl-oracle-') as temp:
        c = Path(temp) / 'ttl.c'
        library = Path(temp) / 'ttl.so'
        c.write_text(source)
        subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-shared', '-fPIC', str(c), '-o', str(library)], check=True)
        lib = ctypes.CDLL(str(library))
        lib.oracle_parse.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_int,
                                     ctypes.POINTER(ctypes.c_uint32)]
        lib.oracle_parse.restype = ctypes.c_int
        lib.oracle_format.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
        lib.oracle_format.restype = ctypes.c_int
        parses = []
        for text in sorted(inputs):
            for counter in [False, True]:
                value = ctypes.c_uint32(0)
                result = lib.oracle_parse(text, len(text), counter, ctypes.byref(value))
                parses.append({'hex': text.hex(), 'counter': counter,
                               'result': RESULTS[result], 'value': value.value})
        formats = []
        for value in sorted(values):
            for verbose in [False, True]:
                for upcase in [False, True]:
                    output = ctypes.create_string_buffer(256)
                    result = lib.oracle_format(value, verbose, upcase, output)
                    assert result == 0
                    formats.append({'value': value, 'verbose': verbose, 'upcase': upcase,
                                    'text': output.value.decode('ascii')})
    data = {'metadata': {'upstream': args.source.name, 'seed': 92027,
                         'method': 'upstream TTL and parseint functions with minimal ISC buffer/result shim',
                         'sources': {p: hashlib.sha256((args.source/p).read_bytes()).hexdigest() for p in paths}},
            'parse': parses, 'format': formats}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, separators=(',', ':')) + '\n')
    print(f'Generated {len(parses)} parse and {len(formats)} format cases from upstream C')


if __name__ == '__main__':
    main()

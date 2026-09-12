#!/usr/bin/env python3
"""Discover upstream test entrypoints statically without importing test code."""
import ast
import json
from pathlib import Path

# These are test-planning groupings, not measured observations of real users.
GROUPS = {
    '权威 DNS 与区域数据': {'auth','additional','builtin','case','class','cname_dname_negcache','emptyzones','glue','masterfile','masterformat','names','rrsetorder','sortlist','ttl','unknown','wildcard','zonechecks','checkzone','checknames','integrity','cap_glues','checkconf','checkconf_keys','include_multiplecfg'},
    '递归、转发与缓存': {'resolver','forward','fwdfirst','bailiwick','cacheclean','expiredglue','fetchlimit','qmin','reclimit','serve_stale','sfcache','sfcache_cname','staticstub','stub','mirror','mirror_root_zone','nta','pending','qpcache_rrsig_any','resend_loop','nsprocessinglimit','selfpointedglue','srtt','cdnxdomain'},
    'DNSSEC 与密钥管理': {'autosign','cds','checkds','dsdigest','ecdsa','eddsa','enginepkcs11','inline','kasp','keyfromlabel','ksr','migrate2kasp','mkeys','multisigner','nsec','nsec3','optout','rfc5011','rootkeysentinel','rsabigexponent','sig0','smartsign','synthfromdnssec','verify'},
    '更新、传送与主从同步': {'addzone','catz','dialup','ixfr','ixfr_nonminimal','journal','notify','nsupdate','nzd2nzf','ssumaxtype','ssutoctou','upforwd','xfer','xfer_servers_list','xferquota','tsig','tkey','tkeyleak','tsiggss'},
    '访问控制与 DNS 策略': {'acl','allow_query','dns64','dns64_dname','filters','geoip2','redirect','rpz','rpzextra','rpzrecurse','rrl','transport_acl','views'},
    '网络传输与协议健壮性': {'cipher_suites','cookie','dispatch','doth','ednscompliance','formerr','keepalive','limits','mismatchtcp','padding','pipelined','proxy','query_source','randomizens','tcp','timeouts','transport_change','zero'},
    '运维管理、诊断与工具': {'digdelv','dnstap','host','idna','logfileconfig','nslookup','rndc','rndc_confgen','rrchecker','runtime','shutdown','statistics','statschannel','tools'},
    '外部扩展与运行环境': {'database','dlzexternal','dyndb','hooks','cpu','stress','selftest','legacy','metadata','camp','chain','nsprocessinglimit','spf'},
}


def category(name):
    if name.startswith(('dnssec', 'nsec', 'rollover')):
        return 'DNSSEC 与密钥管理'
    return next((group for group, names in GROUPS.items() if name in names), '其他上游回归场景')


def catalog(source):
    system = source / 'bin/tests/system'
    suites = []
    for directory in sorted(system.iterdir()):
        if not directory.is_dir():
            continue
        entries = sorted(p for p in directory.glob('tests*') if p.is_file())
        if not entries:
            continue
        functions, errors = [], []
        for file in entries:
            if file.suffix != '.py':
                continue
            try:
                tree = ast.parse(file.read_text())
                # Candidates only: pytest parametrization/markers determine runtime cases.
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                        functions.append({'file': file.relative_to(source).as_posix(),
                                          'function': node.name, 'line': node.lineno})
            except (SyntaxError, UnicodeError) as exc:
                errors.append(f'{file.name}: {exc}')
        suites.append({'suite': directory.name, 'scenario': category(directory.name),
                       'entrypoints': [p.relative_to(source).as_posix() for p in entries],
                       'static_test_function_candidates': functions, 'discovery_errors': errors,
                       'go_status': 'blocked_unimplemented',
                       'reason': 'Go named and BIND command-line tools are not implemented',
                       'upstream_status': 'not_run'})
    return {'baseline': source.name, 'method': 'static source discovery; not pytest collection or execution',
            'suite_count': len(suites),
            'static_function_candidate_count': sum(len(s['static_test_function_candidates']) for s in suites),
            'suites': suites}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    result = catalog(root / 'upstream/bind-9.20.27')
    destination = root / 'docs/full-test-catalog.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f"{result['suite_count']} suites, {result['static_function_candidate_count']} static function candidates")

# BIND 原版全量测试结果

**被测对象为原版 C BIND 9.20.27；Go 全功能测试仍因服务未实现而阻塞。**

原版单元测试程序：93；通过：93；失败：0；错误：0。

合并补测后的系统用例：1063；通过：1055；失败：5；错误：1；跳过：2。

合并以 pytest classname/name 标识为准，后一次结果替代前一次状态；原始运行历史保留在 JSON 中。

| 未通过的用例 | 状态 | 原因 |
|---|---|---|
| keyfromlabel.tests_keyfromlabel::test_keyfromlabel[rsasha256-rsa-2048] | failed | subprocess.CalledProcessError: Command '['/src/bin/dnssec/dnssec-keyfromlabel', '-a', 'rsasha256', '-y', '-l', 'pkcs11:token=softhsm2-keyfromlabel;object=keyfromlabel-zsk-rsasha256.example;pin-source=pin', 'rsasha256.example']' died with <Signals.SIGSEGV: 11>. |
| keyfromlabel.tests_keyfromlabel::test_keyfromlabel[rsasha512-rsa-2048] | failed | subprocess.CalledProcessError: Command '['/src/bin/dnssec/dnssec-keyfromlabel', '-a', 'rsasha512', '-y', '-l', 'pkcs11:token=softhsm2-keyfromlabel;object=keyfromlabel-zsk-rsasha512.example;pin-source=pin', 'rsasha512.example']' died with <Signals.SIGSEGV: 11>. |
| keyfromlabel.tests_keyfromlabel::test_keyfromlabel[ecdsap256sha256-EC-prime256v1] | failed | subprocess.CalledProcessError: Command '['/src/bin/dnssec/dnssec-keyfromlabel', '-a', 'ecdsap256sha256', '-y', '-l', 'pkcs11:token=softhsm2-keyfromlabel;object=keyfromlabel-zsk-ecdsap256sha256.example;pin-source=pin', 'ecdsap256sha256.example']' died with <Signals.SIGSEGV: 11>. |
| keyfromlabel.tests_keyfromlabel::test_keyfromlabel[ecdsap384sha384-EC-prime384v1] | failed | subprocess.CalledProcessError: Command '['/src/bin/dnssec/dnssec-keyfromlabel', '-a', 'ecdsap384sha384', '-y', '-l', 'pkcs11:token=softhsm2-keyfromlabel;object=keyfromlabel-zsk-ecdsap384sha384.example;pin-source=pin', 'ecdsap384sha384.example']' died with <Signals.SIGSEGV: 11>. |
| rpzrecurse.tests_sh_rpzrecurse_dnsrps::test_rpzrecurse_dnsrps | skipped | dnsrps disabled in the build |
| rpz.tests_sh_rpz_dnsrps::test_rpz_dnsrps | skipped | dnsrps disabled in the build |
| enginepkcs11.tests_sh_enginepkcs11::test_enginepkcs11 | error | failed on setup with "Failed: setup.sh exited with 1" |
| mirror_root_zone.tests_mirror_root_zone::test_mirror_root_zone | failed | isctest.log.watchlog.WatchLogTimeout: Timeout reached watching ns1/named.run for transfer\ of\ '\./IN'\ from\ .*#53: Transfer\ status:\ success |

[完整机器报告](upstream-summary.json)

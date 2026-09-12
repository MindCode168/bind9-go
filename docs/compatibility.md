# 功能兼容性清单

基线：BIND 9.20.27。以下为工作分组，不是已证明完整的功能枚举；
还须从配置语法、工具手册、编译选项和系统测试补充细项。

| 功能 | 上游主要位置 | 当前状态 |
|---|---|---|
| 32 位序列号的六种比较 | lib/isc/serial.c | Go 实现及原版 C 对照数据已建立；测试结果见 README |
| TTL/counter 文本解析及格式化 | lib/dns/ttl.c | 28,286 个差分用例通过，并对照完整 libdns 验证；未实现有限缓冲区接口 |
| DNS 名称、压缩、报文、RR 类型和 EDNS | lib/dns | 未移植 |
| named.conf、include、检查和诊断 | lib/isccfg、bin/check | 未移植 |
| zone 文本、raw 格式、journal | lib/dns | 未移植 |
| UDP、TCP、TLS、HTTPS、连接限制 | lib/isc、lib/dns、bin/named | 未移植 |
| 权威区域、委派、通配符、CNAME/DNAME | lib/ns、lib/dns | 未移植 |
| 递归、转发、缓存、负缓存、serve-stale | lib/dns/resolver.c、lib/dns | 未移植 |
| DNSSEC 验证、NSEC/NSEC3、信任锚、RFC5011 | lib/dns | 未移植 |
| AXFR/IXFR、NOTIFY、主从、catalog zones | lib/dns、lib/ns | 未移植 |
| 动态更新、TSIG、TKEY、GSS-TSIG | lib/dns、lib/ns、bin/nsupdate | 未移植 |
| 自动签名、密钥策略、轮换、PKCS#11 集成 | lib/dns、bin/dnssec | 未移植 |
| views、ACL、RPZ、RRL、DNS64、GeoIP | lib/dns、lib/ns、bin/named | 未移植 |
| RNDC 协议、在线重载与管理 | lib/isccc、bin/rndc、bin/named | 未移植 |
| 日志、统计、统计通道、dnstap | lib/isc、lib/dns、bin/named | 未移植 |
| dig、host、nslookup、delv | bin/dig、bin/delv | 未移植 |
| named-checkconf、named-checkzone、compilezone | bin/check | 未移植 |
| dnssec-*、nsupdate、rndc、confgen 和其他工具 | bin/dnssec、bin/nsupdate、bin/rndc、bin/confgen、bin/tools | 未移植 |
| DLZ、dyndb、插件接口、外部依赖 | lib/dns、bin/plugins、configure.ac | 未移植 |
| 启动参数、守护进程、权限、平台行为 | bin/named、lib/isc | 未移植 |

`source-inventory.json` 保存每个 C/H 文件的哈希和初始未移植状态。
`system-test-inventory.json` 保存系统测试入口的初始未运行状态。
文件存在不代表测试通过；所有服务级行为目前均未验证。

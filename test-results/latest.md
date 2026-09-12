# 当前全功能测试报告

运行标识（UTC）：20260912T163203Z

**全功能验收未通过。已实现模块检查结果如下；174 个系统测试套件因服务功能未实现而阻塞。**

| 已执行检查 | 结果 | 日志 |
|---|---|---|
| toolchain | passed | [toolchain.log](20260912T163203Z/toolchain.log) |
| unit-race-coverage | passed | [unit-race-coverage.log](20260912T163203Z/unit-race-coverage.log) |
| coverage-functions | passed | [coverage-functions.log](20260912T163203Z/coverage-functions.log) |
| vet | passed | [vet.log](20260912T163203Z/vet.log) |
| fuzz-FuzzCompare | passed | [fuzz-FuzzCompare.log](20260912T163203Z/fuzz-FuzzCompare.log) |
| fuzz-FuzzRoundTrip | passed | [fuzz-FuzzRoundTrip.log](20260912T163203Z/fuzz-FuzzRoundTrip.log) |
| fuzz-FuzzParse | passed | [fuzz-FuzzParse.log](20260912T163203Z/fuzz-FuzzParse.log) |

| 用户场景分组 | 阻塞的系统测试套件数 |
|---|---|
| DNSSEC 与密钥管理 | 50 |
| 外部扩展与运行环境 | 12 |
| 更新、传送与主从同步 | 19 |
| 权威 DNS 与区域数据 | 24 |
| 网络传输与协议健壮性 | 18 |
| 访问控制与 DNS 策略 | 13 |
| 运维管理、诊断与工具 | 14 |
| 递归、转发与缓存 | 24 |

套件数不等于运行时测试用例数；参数化、跳过条件及环境依赖由 pytest 在实际运行时决定。
本次未使用真实用户数据，未对用户生产 DNS 发起测试。
上游 C 基准环境的构建情况另见 docs/full-testing.md。
短时模糊测试、语句覆盖率和差分样本通过均不能证明整个 BIND 已兼容。

[机器可读报告](20260912T163203Z/report.json)

# BIND 9.20.27 / Go 移植测试报告

日期：2026-09-13（Asia/Shanghai）。**测试已执行，整体未通过全功能验收。**

| 被测范围 | 结果 |
|---|---|
| 原版 C 单元测试程序 | 93 / 93 通过，无跳过、失败或错误 |
| 原版系统测试，含针对性补测 | 1,063 个用例：1,055 通过、5 失败、1 错误、2 跳过 |
| 当前两个 Go 包（serial、ttl） | macOS arm64 与 Linux arm64 均通过；macOS 竞态检查和 go vet 通过 |
| C/Go 差分样本 | 序列号 8,273 对输入（每对六种比较）；TTL 20,046 个解析、8,240 个格式化用例通过 |
| 完整原版库二次对照 | 上述全部差分样本与实际编译的 libdns/libisc 一致 |
| Go 模糊测试 | 三项各 10 秒通过：序列号、TTL 往返、任意 TTL 输入解析 |
| Go 语句覆盖率 | 当前两个包 100%；不代表 BIND 全功能覆盖率 |
| Go 产品级系统测试 | 174 个套件阻塞：Go named、命令行工具等服务功能未实现 |

## 未通过的内容

- **4 个失败、1 个错误：PKCS#11/SoftHSM。** provider 1.2.0 测试环境中，
  RSA-SHA256、RSA-SHA512、ECDSA-P256、ECDSA-P384 的 dnssec-keyfromlabel 调用 SIGSEGV；
  enginepkcs11 的 setup.sh 失败。组件根因尚未确定，见 [诊断记录](../docs/pkcs11-test-failures.md)。
- **1 个失败：公网根区镜像。** 重现日志显示 AXFR 收到 8 条消息、2,320 条记录、
  132,490 字节后以 EOF 结束，未出现成功状态，随后测试等待超时。
  这是本次公网传送失败的证据，不足以单独归因为 BIND 核心缺陷。
- **2 个跳过：DNSRPS。** 构建未启用外部 DNSRPS provider；不能将内置 RPZ 测试通过
  视为外部 DNSRPS 接口已验证。需要提供并配置实际 provider 后补测。

SSLyze、GnuTLS、1 分钟空闲超时、5 分钟传送超时及公网 RFC 5011 刷新均已补测通过。
原版全量首轮耗时约 15 分钟；两项长测和 TLS 补测合计约 7 分钟。

## 证据与复现

- [原版系统用例汇总与失败明细](upstream-summary.md)
- [原版机器可读汇总，保留各轮历史](upstream-summary.json)
- [当前 Go 测试报告与原始日志](latest.md)
- [Linux 完整库差分结果](linux-arm64-20260913/compiled-upstream-oracle.log)
- [Linux Go 序列号测试](linux-arm64-20260913/serial.log)、[TTL 测试](linux-arm64-20260913/ttl.log)
- [公网根区 AXFR 原始日志摘录](upstream-mirror-diagnostic-20260913/named-transfer-excerpt.log)
- [功能场景、容器构建和执行说明](../docs/full-testing.md)

系统用例按 pytest classname/name 合并，补测结果替代同名用例的首轮状态，不重复累计。
失败的 provider 镜像预检单独保留于 `environment/`，没有伪装成已运行的系统用例。
本次使用公开源码、合成测试配置和公开根区数据，没有使用真实用户生产配置或流量。

GitHub 私有仓库 `bind9-go` 的创建条件仍为完整移植完成并通过验收；当前尚不满足。

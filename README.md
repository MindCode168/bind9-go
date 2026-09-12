# BIND → Go 移植工程

**未完成，不能替代 BIND，也没有可启动的 DNS 服务。**

目标：完整移植 ISC BIND，保留全部功能。基线为 2026-09-13 查询到的最新稳定版
[BIND 9.20.27](https://www.isc.org/download/)；官方同时发布的 9.21.25 为开发版。

## 当前交付

- 官方源码位于 `upstream/bind-9.20.27/`，已核对源码版本并记录本地 SHA-256。
  尚未验证 OpenPGP 签名，本地哈希不等于签名验证。
- 源码总计 5,224 个文件，883 个 C/H 文件，463,998 行 C/H 文本（含测试、注释和空行）。
- 已盘点 174 个包含 `tests*` 文件入口的系统测试目录，原版系统测试结果见下方验证报告；Go 服务端仍未实现。
- `internal/serial`：序列号六种比较操作，以及显式返回未定义错误的比较和加法接口。
  已用原版 C 函数生成 8,273 组差分测试数据，包含回绕和半范围歧义。
- `internal/ttl`：TTL/counter 文本解析及 TTL 格式化。保留 BIND 的单位大小写、
  重复单位、零值和溢出行为；输出使用 Go 字符串，尚未实现 C 有限缓冲区的写入接口。

## 验证

完整执行结论见 [测试总报告](test-results/REPORT.md)：原版 1,063 个系统用例合并补测后，
1,055 通过、5 失败、1 错误、2 跳过；原版 93 个单元测试程序全部通过。

两个包已通过竞态检测下的单元测试、go vet 和三项各 10 秒模糊测试，当前语句覆盖率 100%。
序列号模块通过 8,273 组原版 C 差分输入；TTL 通过 20,046 个解析和 8,240 个格式化差分用例。
全部差分样本还对照了 Linux 中完整编译的原版 libdns/libisc，结果一致；
两个 Go 包均已在 macOS arm64 和 Linux arm64 上运行通过。
详见 [最新执行报告](test-results/latest.md) 和 [全功能测试说明](docs/full-testing.md)。
两个基础模块通过不代表 DNS 服务行为兼容；174 个 Go 系统测试套件仍因未实现而阻塞。

需要 Go 1.24 或更新版本；无第三方 Go 依赖。

```sh
make test
make vet
make fuzz
make test-report
```

如使用本地独立工具链，可传入 `make GO=/absolute/path/to/go test`。
`make oracle` 需要 Python 3、clang 和已解压的基线源码。
`make inventory` 生成新的盘点文件，不覆盖已维护的移植状态。
`make release-check` 在全功能未完成时明确返回非零，不允许基础包通过掩盖服务级缺口。

## 后续实施依据

DNS 性能实测见 [HTML 性能报告](performance-results/20260913/report.html) 和
[压测复现说明](benchmarks/README.md)：已完成 BIND 的 36 轮实测，Go 因没有 DNS 服务端而不可测，尚不能进行双实现性能比较。

- [移植决策和验收要求](docs/ADR-001-port-strategy.md)
- [功能兼容性清单](docs/compatibility.md)
- [逐文件源码清单](docs/source-inventory.json)
- [系统测试入口清单](docs/system-test-inventory.json)
- [完整系统测试目录及实际状态](docs/full-test-catalog.json)
- [上游版本和源码哈希](docs/upstream.json)

下一阶段需要移植 DNS 名称、报文/RR 编解码及配置解析。原版 named 的可运行测试环境已建立；
Go 的递归解析、DNSSEC、区域传送、动态更新、RNDC 和命令行工具等仍未实现。

源码许可证见 `LICENSE`；ISC 上游版权信息保存在 `UPSTREAM-COPYRIGHT`。
该项目不是 ISC 官方 Go 发行版。

## GitHub 仓库

私有仓库：`MindCode168/bind9-go`，主干：`main`。
当前提交为移植中的开发快照，完整实现和兼容性验收尚未完成。
仓库包含 Go 源码、许可证、文档、必要测试数据及实际执行报告；
排除下载的上游源码、工具链、缓存和临时文件。

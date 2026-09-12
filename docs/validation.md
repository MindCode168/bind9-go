# 实际验证记录

本文件保留初次移植的历史验证。后续新增 TTL 差分和解析模糊测试结果见
[最新执行报告](../test-results/latest.md)；以下“未执行”是首次测试时的状态。

日期：2026-09-13；平台：macOS arm64；工具链：Go 1.27.1。

工具链来自 Go 官方下载，SHA-256 与官方下载页面一致：
`ee215d57e0ec269c60cc9ceca68e6bda321ba9ee5afe24f4b0988703c2d87d12`。
工具链安装在项目 `.cache/toolchain/go/`，未修改系统 Go 安装。

执行命令（项目根目录）：

```sh
make GO="$PWD/.cache/toolchain/go/bin/go" test vet fuzz
```

| 检查 | 结果 | 范围 |
|---|---|---|
| go test -race ./... | 通过 | serial、ttl 两个包 |
| 原版 C 序列号比较差分 | 通过 | 8,273 对输入，每对比较六种运算 |
| go vet ./... | 通过 | 当前两个 Go 包 |
| FuzzCompare，5 秒 | 通过 | 932,337 次执行，序列号反对称性和递增关系 |
| FuzzRoundTrip，5 秒 | 通过 | 925,976 次执行，TTL 格式化/解析往返 |
| Python AST、JSON 解析 | 通过 | 工具脚本和清单语法 |

未执行：原版 named 编译、DNS 服务系统测试、TTL 原版 C 差分、网络协议模糊测试、
跨平台测试、生产负载测试。上述短时模糊测试不能证明不存在缺陷。

TTL 目前适配成 Go 字符串返回值；原版 C 有限缓冲区写入和 NOSPACE 行为没有对应实现。
这两个包的验证结果不构成完整 BIND 移植或服务可替换性证明。

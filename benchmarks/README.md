# DNS 性能基线与对比报告

[2026-09-13 HTML 报告](../performance-results/20260913/report.html) 包含 BIND 9.20.27 的真实压测。
Go 工程当前只有 `internal/serial` 和 `internal/ttl`，没有 DNS 服务端；因此 Go 的所有服务性能指标为不可测，尚不能给出两种实现的性能倍数或胜负。

## 本次测量

- BIND 9.20.27 源码测试构建，Ubuntu 24.04.5 LTS / Linux arm64，dnsperf 2.14.0（包版本 `2.14.0-1build2`）。完整构建参数、依赖版本和镜像 ID 保存在结果中。
- Apple M4 / 16 GiB，Docker VM 可用 10 个逻辑 CPU；服务端固定到 0、1，客户端固定到 2、3。使用单容器 IPv4 回环、`--network none`，查询不发往外部 DNS。
- UDP、TCP × A 命中、NXDOMAIN × 10,000、50,000、100,000 目标 QPS × 3 次重复，共 36 次正式测量。每轮独立预热 2 秒，再测量 5 秒，执行顺序按种子 92027 随机排列。
- 单个 unsigned 权威区，区域总计 10,003 条 RR，其中 10,000 条是被查询的 A 记录。关闭递归和查询日志；TCP 每轮建立新连接后复用。
- 实际发送和完成 QPS、平均延迟、未完成比例、服务进程 CPU、采样峰值 RSS 分别统计；每组报告中位数及最小–最大范围。延迟不包含未完成查询。

这不是最大容量测试、长期稳定性测试、完整功能测试或生产 SLA 验证。宿主机背景活动及一个既有容器没有停止。全部已收到响应的 RCODE 符合预期；完整内容仅通过压测前的代表性查询检查，未逐一校验所有响应。

## 复现压测

在项目根目录运行，需要 Docker、至少四个可分配的逻辑 CPU，以及本地已解压的上游源码。压测启动的 DNS 服务仅供容器内测试。

```sh
docker build --progress=plain -t bind9-go-upstream-test:9.20.27 \
  -f tests/upstream.Dockerfile upstream/bind-9.20.27
docker build -t bind9-go-benchmark:9.20.27 -f benchmarks/Dockerfile benchmarks
mkdir -p performance-results/new-run
docker run --rm --network none --cpuset-cpus=0-3 \
  --mount "type=bind,source=$PWD/benchmarks,target=/bench,readonly" \
  --mount "type=bind,source=$PWD/performance-results/new-run,target=/results" \
  bind9-go-benchmark:9.20.27 python3 /bench/run_benchmark.py \
  > performance-results/new-run/runner.log 2>&1
python3 benchmarks/render_report.py \
  performance-results/new-run/benchmark.json \
  performance-results/new-run/report.html
```

HTML 生成器需要 Python 3 和 Matplotlib；HTML 阅读本身无依赖，可以离线打开。可筛选表格、下载内嵌 JSON、打印。生成器检查完整运行的协议、查询、速率和重复矩阵，拒绝假冒实测的示例值和重复记录。

构建使用的软件源会变化；精确追溯本次测量以结果中的镜像 ID、`packages.txt`、`named-version.txt` 和配置哈希为准，不能假设未来构建得到相同镜像。新运行的宿主机环境需重新采集，不应复制本次环境信息。

## 文件说明

- `run_benchmark.py`：启动原版 named、检查代表性查询、运行 dnsperf、采样 CPU/RSS 并保存日志。
- `render_report.py`：仅从实际 JSON 生成离线 HTML，无模拟或虚构的 Go 数据。
- `report-schema.json`：数据形状示例，**不是正式 JSON Schema，也不是测试结果**。
- 结果目录中的 `run_benchmark.executed.py` 是本次实际执行的脚本快照；之后仅修正记录总数字段及 CPU 时间窗口说明，测量数据未改。
- `host-environment.json` 与 `go-package-inventory.txt` 为独立采集的环境和 Go 服务缺失证据。
- `logs/*-warmup.log` 不进入统计；`logs/*.log` 为 36 轮正式输出；`logs/*-resources.json` 为资源中间采样。
- `parser-smoke-diagnostic.log` 是正式压测前的解析器诊断，不算正式测量。

CPU 由执行时读取的进程 user/system tick 差计算，100% 表示一个逻辑核；采样窗口约 5.153–5.183 秒，包含客户端启动和退出等待，略长于 dnsperf 的统计窗口。中间样本已保存，但精确 CPU 起止端点未单独落盘，所以不能只凭中间样本完全重建报告中的同一端点值。

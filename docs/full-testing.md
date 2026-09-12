# 全功能测试范围和执行说明

本次实际执行结论和未通过项见 [测试总报告](../test-results/REPORT.md)。

## 范围

依据本地 BIND 9.20.27 官方源码及其测试套件制定用户场景；没有采集真实用户数据，
没有连接生产 DNS。目标仍是完整移植和完整兼容性验收，不能仅凭基础包覆盖率发布。

测试分三层：

1. 原版 C 基准：构建 BIND 并执行 CMocka 和上游 pytest 系统测试，记录环境相关的跳过。
2. 当前 Go 实现：序列号和 TTL 的边界、错误、C 差分、竞态、覆盖率、模糊测试。
3. 产品级兼容：使用 Go named 和 Go 命令行工具执行全部上游场景。
   当前缺少这些实现，174 个系统测试套件全部处于阻塞状态。

## 用户场景验收

| 场景 | 核心行为和故障路径 | 测试依据 |
|---|---|---|
| 托管权威域名 | 所有 RR、委派、通配符、CNAME/DNAME、否定应答、zone 格式与诊断 | auth、wildcard、masterfile、unknown、zonechecks |
| 企业递归 DNS | 真实迭代、转发回退、缓存与过期、负缓存、委派边界、资源上限 | resolver、forward、bailiwick、serve_stale、reclimit |
| 签名区域和验证 | 有效/无效/过期签名、NSEC/NSEC3、信任锚、密钥轮换 | dnssec*、nsec*、kasp、rollover*、rfc5011 |
| 主从与动态更新 | AXFR/IXFR/NOTIFY、更新权限、认证失败、journal 和重启恢复 | xfer、ixfr、notify、nsupdate、journal、tsig |
| 多租户和策略 | views、ACL、RPZ、RRL、DNS64、GeoIP | views、acl、rpz*、rrl、dns64*、geoip2 |
| 网络客户端兼容 | UDP 截断/TCP 回退、EDNS、cookie、TLS/HTTPS、错误和畸形报文 | tcp、ednscompliance、cookie、doth、formerr |
| 运维人员使用 | 配置检查、RNDC、日志、统计、重载、dig/host/nslookup/delv/nsupdate | checkconf、rndc、statschannel、digdelv、host、nslookup |
| 扩展和运行环境 | DLZ、dyndb、插件、GSSAPI、硬件密钥、并发与压力 | dlzexternal、dyndb、hooks、tsiggss、enginepkcs11、stress |

这些分组是工程测试分类，不是实测用户画像。每个上游套件均列于
`full-test-catalog.json`；静态函数候选数不等于 pytest 实际参数化后的用例数。

## 当前 Go 测试

```sh
make GO="$PWD/.cache/toolchain/go/bin/go" test-report
make GO="$PWD/.cache/toolchain/go/bin/go" release-check
```

第一条生成当前已实现模块的执行报告。第二条同时检查全功能验收条件，
在服务功能未实现时明确以非零退出码结束。未实现项不得用 skip 替代后计为成功。
当前全功能门槛固定为未满足，完成移植时还必须接入真实系统测试结果才能解除。

结果在 `test-results/latest.md` 和对应 UTC 运行目录，保留命令、退出码、日志、
语句覆盖率文件和被测源码哈希。

## 原版基准环境

官方系统测试要求虚拟 IPv4/IPv6 地址。只在一次性容器内部建立测试网络，
不使用宿主机网络模式，不发布 53 端口，不修改宿主机网络。

```sh
docker build --progress=plain -t bind9-go-upstream-test:9.20.27 \
  -f tests/upstream.Dockerfile upstream/bind-9.20.27
mkdir -p test-results/upstream
docker run --rm --cap-add NET_ADMIN \
  --mount "type=bind,source=$PWD/test-results/upstream,target=/results" \
  --mount "type=bind,source=$PWD/tests/run-upstream.sh,target=/run-upstream.sh,readonly" \
  bind9-go-upstream-test:9.20.27 bash /run-upstream.sh
```

如 Docker Hub 不通，可增加
`--build-arg BASE_IMAGE=public.ecr.aws/ubuntu/ubuntu:24.04`。
这是 [Ubuntu 官方列出的镜像来源](https://ubuntu.com/docs/oci-registries/oci-how-to/getting-started/)。
镜像 tag 和依赖版本并非永久固定，执行时保存 `named -V`、系统包和 Python 包版本，
并应在后续稳定 CI 中锁定镜像 digest。

容器运行原版 CMocka 和全量 pytest（4 个 worker，系统测试上限 30 分钟）。
超时、跳过、失败、收集错误均单独记录；不能等同全功能通过。
原版 C 测试通过也不能替代 Go 兼容性测试。

## 针对性补测

`tests/extended.Dockerfile` 补充 SSLyze、GnuTLS、SoftHSM 工具并启用长测。
使用 `tests/run-selected.sh` 接收 pytest 路径或 node ID，日志和 JUnit 输出至独立 `/results`。
网络补测使用默认 `/etc/ssl/openssl.cnf`，实际 5 个用例全部通过。
公网测试通过 `CI_ENABLE_LIVE_INTERNET_TESTS=1` 启用，只查询公开根区。

PKCS#11 的 provider 镜像和两个版本的预检均保留，当前未通过情况见
[PKCS#11 诊断记录](pkcs11-test-failures.md)，不能当作已就绪环境使用。

使用 `tools/summarize_upstream.py` 传入按时间排序的已完成结果目录，可重新合并 JUnit，
生成 `test-results/upstream-summary.json` 并更新每个上游套件的状态。
补测不覆盖首轮原始日志，不修改上游断言以获得通过。

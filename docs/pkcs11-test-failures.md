# PKCS#11 扩展测试未通过

被测对象：原版 C BIND 9.20.27，Ubuntu 24.04 arm64，OpenSSL 3.0.13，SoftHSM。
这些结果不是 Go 实现错误，也尚不足以确认错误属于 BIND、provider 或其组合配置。

## 已观察结果

| 环境 | 实际结果 |
|---|---|
| 旧 PKCS#11 engine 配置 | feature-test --md5 在 pytest 初始化阶段触发 dst_initialized 断言，测试未收集 |
| provider 1.2.0，minimal 配置 | 测试已执行：4 个 dnssec-keyfromlabel 用例 SIGSEGV，enginepkcs11 的 setup.sh 失败 |
| provider 1.2.0，按 BIND 文档设置 early/no-deinit | 镜像构建的 feature-test --md5 预检 SIGSEGV，未运行测试 |
| provider 0.6，设置 early/no-deinit | 同样在镜像预检 SIGSEGV，未运行测试 |

provider 1.2.0 的 minimal 配置用例包括 RSA-SHA256、RSA-SHA512、ECDSA-P256 和 ECDSA-P384。
失败运行的 JUnit、pytest 日志和版本清单在 `test-results/upstream-provider-20260913/`。
初始化失败记录在 `test-results/upstream-extra-20260913/`。

## 重现和后续定位

`tests/provider.Dockerfile` 的默认配置为 BIND 文档推荐的 early/no-deinit，当前已知会在预检失败。
这项失败检查被保留，不通过删除检查让镜像看起来成功。
要重现已执行的 4 个失败和 1 个错误，构建时使用：

```sh
docker build -t bind9-go-upstream-provider:reproduce \
  --build-arg PROVIDER_VERSION=1.2.0 \
  --build-arg PROVIDER_CONFIG=openssl-provider-minimal.cnf \
  -f tests/provider.Dockerfile tests
```

然后使用 `tests/run-selected.sh` 在隔离容器中运行 `keyfromlabel enginepkcs11`。
下一步需要在相同环境中保留 core/backtrace，定位首次无效访问，并对照 BIND 官方 CI 的
OpenSSL/provider/SoftHSM 版本组合。不能在缺少回溯证据时将原因定为某个组件缺陷。

依据：BIND 源码 `doc/arm/pkcs11.inc.rst` 的 provider 配置说明；
[provider 官方构建说明](https://github.com/openssl-projects/pkcs11-provider/blob/v1.2.0/BUILD.md)。

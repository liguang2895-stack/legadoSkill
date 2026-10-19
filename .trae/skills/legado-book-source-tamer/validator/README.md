# 内嵌验证器（第三方组件）

## 来源与许可

- 文件：`app/legado-source-validator.jar`
- 来源项目：`book-source-creator-skill`（Narylr350/book-source-creator-skill，MIT License）
- 本项目内**原样使用，未做任何修改**。

该 jar 是一个 Kotlin/JVM 实现的 Legado 书源规则验证器，复刻阅读 App 的规则引擎核心语义：

- Jsoup CSS 选择器、XPath、JSONPath、正则、Rhino（ES6）JS 执行
- 搜索 → 详情 → 目录 → 正文四链路验证
- HTTP 请求走系统 `curl`（避开 PC JVM TLS 指纹被反爬识别）
- 结构化 errorCode（CAPTCHA_DETECTED / CONTENT_IS_CSR_SHELL / CONTENT_IS_VIP_LOCK_PAGE 等）

## 运行要求

- Java 21+（jar 为 Java 21 字节码，class major 65）
- 系统 `curl`（Windows 10+ 自带）
- 不需要 adb / Android（`mode=http` 完全独立运行）

## 用法

统一由本技能脚本管理，不要手工 `java -jar`：

```bash
python scripts/validator_run.py setup-jre    # 首次：检测/自动下载便携 JRE 21
python scripts/validator_run.py start        # 启动（自动选端口，写 .runtime.json）
python scripts/validator_run.py status       # 查看运行状态
python scripts/validator_run.py stop         # 停止
```

验证书源请使用 `scripts/verify_source.py`（封装了四链路验证、报告生成与 hash 门禁）。

## HTTP API 速查（validator_run.py / verify_source.py 内部使用）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sources` | 就绪探针，返回已导入源列表 |
| POST | `/api/debug/run` | 单次四链路验证，body：`{sourceJson, sourceUrl, keyword, mode, debugDir}` |
| POST | `/api/validate-rules` | 静态规则校验（dry-run） |
| POST | `/api/cookie/set` | 注入 Cookie：`{domain, cookie}` |
| GET | `/api/cookie/list` | 列出已存 Cookie |

服务仅绑定 `127.0.0.1`。

## 注意

- 验证码 / Cloudflare / 登录墙 / 付费墙站点会被 validator 如实识别为对应 errorCode。这是站点固有限制，不是书源规则错误，**禁止反复重试**（反复探测会累积触发 IP 级风控）。
- `mode=http` 验证通过代表"规则层在等价引擎下跑通"，不等于 Android 阅读 App 实测通过；涉及 WebView / 登录态的书源仍需真机复核。

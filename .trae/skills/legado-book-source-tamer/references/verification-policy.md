# 验证策略与交付门禁

> 核心原则：**结论不能强过证据。** 报告只能由脚本生成，交付话术只能引用报告状态。

## 验证分级

| 等级 | 工具 | 证明什么 | 不证明什么 |
|------|------|----------|-----------|
| **L1 静态审计** | `rule_audit.py` | 没有已知静态错误（占位符、非法字段、语法错误、结构缺失） | 规则能否命中真实站点 |
| **L2 真引擎验证** | `verify_source.py`（内嵌 Kotlin validator） | 规则在 Legado 规则引擎等价实现下，四链路（搜索→详情→目录→正文）真实跑通 | Android WebView 行为、登录态、App 最终体验 |
| **L3 App 实测** | 用户在 Legado APP 导入 | 最终真实可用性 | — |

**交付门槛**：L1 必须过；L2 必须跑并产出报告。只有 L2 `passed` 才能说"可交付"；`partial`/`degraded` 只能按降级话术交付；L3 永远由用户完成，交付说明必须提醒。

## 标准流程

```bash
# 1. 静态审计（写规则后立即跑）
python scripts/rule_audit.py <书源.json>

# 2. 真引擎验证（交付前必跑；自动启动 validator）
python scripts/verify_source.py <书源.json> -k "实测关键词"

# 搜索被反爬阻塞时，跳过搜索验证后续链路
python scripts/verify_source.py <书源.json> --book-url "<详情页URL>"

# 3. 交付前复核（改了源文件后旧报告自动失效）
python scripts/verify_source.py <书源.json> --check
```

## verify-report.json 报告契约

| 字段 | 说明 |
|------|------|
| `_generatedBy` | 必须是 `verify_source.py`；手写报告无效 |
| `_sourceHash` | 生成报告时的源文件 sha256；源文件任何改动都会使报告失效 |
| `status` | `passed` / `partial` / `degraded` / `blocked` / `failed` / `error` |
| `phases` | 四链路各自 `success`/`error` |
| `acceptance` | 验收标准逐条结果（search 有结果、detail 有书名、toc 有章节、content ≥100 字） |
| `blocker` | 阻塞类型（见下表），非空时禁止硬凑通过 |
| `steps` | 每步请求/响应/规则命中详情，用于回修定位 |

**禁止行为**：
- 手写或改写报告结论
- 改了源文件后复用旧报告
- 局部链路成功写成"全链路可用"
- 用"总结表格"替代验证

## blocker 处理表

| blocker | 含义 | 处置纪律 |
|---------|------|----------|
| `captcha` | 验证码/人机验证 | **禁止换关键词、换 mode 反复重试**（反复探测会累积 IP 级风控）。**先排查是否为无感 PoW（ALTCHA 类）**：页面无验证码组件但接口 403 时，搜 JS 找 challenge/verify 接口，按 `encrypted-api-altcha.md` 本地求解免人工换 token；确为交互式验证码再让用户手动过验证后重试一次；仍被拦则按失败如实交付。**注意排查 validator 误报**（见下方"validator 已知误报"）|
| `cloudflare` | Cloudflare/Turnstile 拦截 | App 同样会被拦，这是站点固有限制，按失败交付，不协助绕过。**例外**：若业务接口本身不经过盾（盾只挡 HTML 页面），复刻协议直连接口即可绕过，不算"绕过盾"——见 `encrypted-api-altcha.md` |
| `vip` | 付费/VIP 锁 | 收敛为 `degraded`：免费章节能力可交付，必须标注，不得写 full pass |
| `login` | 需要登录态 | 检查 `loginUrl` + `enabledCookieJar: true` + `java.getCookie` header 三件套；无法登录则如实标注 |
| `csr` | 正文依赖 WebView/JS 渲染 | 本地 HTTP 验证不完整，交付必须标注"需 App 实测确认"，不得声称已验证。**注意**：加密 API 站的正文本地解密不依赖 WebView，若协议已用 Python 验证，可在报告中标注"协议级验证通过，WebView 无关" |
| `network` | 网络/环境问题 | 先排除本机代理、DNS、站点可达性，再判定站点问题 |

## validator 已知误报（识别与处置）

validator 的检测逻辑与真机 Legado 有差异，以下情况**不是书源问题**，不要盲目回修：

### 1. toc 阶段误报 CAPTCHA（页面含举报/评论验证码表单）

**症状**：`detail` 阶段同一 URL 成功、`toc` 阶段报 `CAPTCHA_DETECTED`；响应体是正常详情页。
**根因**：validator 在 toc 阶段**执行规则前**扫描页面，命中网站自带的纠错举报/评论表单：
`<div class="captcha">`、`<img src="/captcha.html">` → 触发检测正则
`(?i)(id|class|name)=["'][^"']*captcha[^"']*["']` 和 `(?i)(/|_|-|\b)captcha(\.php|\.jpg|\.png|/|_|-|\b)`。
**判定证据**（决定性）：把 toc 规则换成**纯静态**（如 `var a=[];a.push(JSON.stringify({title:'X',url:'/x.html'}));a`）——
若仍报 CAPTCHA，说明拦截发生在规则执行前，是 validator 误报，不是规则问题。
**处置**：改用**真 Rhino 引擎验证**（见下节"规则级真引擎验证台"），并在报告中如实标注"validator toc 阶段误报，已用 Rhino 验证"。

### 2. URL+options 嵌套解析限制

validator 的 URL 解析正则 `,\{[^}]*\}$` **不支持嵌套花括号**（真机 GSON 支持）。
`{"method":"POST","body":"...","headers":{...}}` 里的嵌套 `headers` 会让 validator 解析失败。
**规避**：options 能不带 headers 就不带（很多 API 不需要）；必须带时验证用真 Rhino。

## 规则级真引擎验证台（validator 不可用时的替代证据）

当 validator 误报/受限时，用 validator JAR 里**自带的真 Rhino 引擎**（与 Legado 同引擎）直接验证单条规则。
参考实现：`references/case-studies/猫扑小说-案例笔记.md` 的 harness 一节（含完整可复用脚本）。
要点：
- 用 `java -cp legado-source-validator.jar org.mozilla.javascript.tools.shell.Main harness.js` 启动；
- harness 里用 java.* 真实现模拟 Legado 行为：`java.net.URL` 发请求、`javax.crypto` 做 AES、
  **手动实现 form 编码**（等价 `analyzeFields`：`k + "=" + URLEncoder.encode(v)`）；
- 用 `eval(ruleSrc)` 在带 `java` mock 的作用域里跑规则，输出章节数/顺序做断言。
- 该验证可作为 L2 的补充证据写入报告（标注"validator 误报，Rhino 规则级验证通过"），但不能替代 L3。

## 回修动作参考

| 失败表现 | 定位 | 回修 |
|----------|------|------|
| URL 没拼对（no scheme） | steps[].request.url | 修 searchUrl/bookUrl/chapterUrl，补 baseUrl |
| 字段没命中 | steps[].ruleHits 中 success=false | 修对应规则字段（CSS/JSONPath/Regex），用 `rule_validator.py` 在已保存 HTML 上验证 |
| 编码乱码 | bodyPreview 乱码 / error 含 charset | 补 `charset`（GBK 站必须配） |
| POST/body 错 | request.method/body 不符 | 修 URL options 的 method/body |
| 目录为空 | toc 步骤 | 检查 chapterList 选择器、tocUrl 是否需要、目录是否分页 |
| 正文太短 | content 步骤 contentLength | 检查 content 选择器、正文是否多页（nextContentUrl） |
| 两章内容相同 | CONTENT_DUPLICATE_BETWEEN_CHAPTERS | 章节 URL 规则错误（都指向同一页） |
| 加密站 401/签名被拒 | error 含 401 / 签名 | 会话过期或签名串错——对照 `encrypted-api-altcha.md` §三/§七，检查时间戳、nonce、bodyHash、五头齐全 |
| 加密站 403/人机验证 | error 含 403 / code 4001 | 未带 captcha_token 或 token 过期——检查 §二 本地 PoW 与 token 缓存（300s） |
| 密文解出乱码 | content 乱码/异常 | `key_mode=chapter` 时未重派生章节密钥——检查 §四 salt 拼接（book_id/chapter_id/version/nonce） |
| API 昨天通今天 `code:-1`/拒绝 | 密钥每日轮换 | 详情页随机名 JS 里提取密钥/IV，动态使用（见 js-api.md 动态密钥一节）；先用 HAR 密文验证算法是否仍为同一算法 |
| 目录章数对但顺序乱/缺后半 | 分页重叠 + 兜底未排序 | 合并多页按主键去重；兜底目录从 URL 提取章号排序（见 js-api.md） |
| validator toc 报 CAPTCHA 但 detail 同页通过 | validator 误报（举报表单） | 用纯静态 toc 规则复测确认；改用 Rhino 规则级验证台（见上文） |

## 反爬与探测纪律

1. **验证码不重试**：命中 captcha 后禁止自动重跑、换关键词、换 mode。
2. **探测有副作用**：反复访问反爬端点会累积风控，可能导致之后连正常浏览器都弹验证。
3. **桌面 ≠ Android**：validator（PC curl）通过只代表规则层跑通；阅读 App 在 Android WebView 环境可能有不同行为（UA、TLS、Cookie）。
4. **SSR/CSR 判定看原始响应**：浏览器看到的是渲染后 DOM，不能据此判定站点是 SSR。
5. **UA 必须完整**：书源 header 的 UA 需含引擎名+版本号（`(KHTML, like Gecko) Chrome/xx Safari/xx`），截断 UA 会被反爬识别。
6. **加密 API 站先协议级验证再交付**：Python 复刻协议全链路跑通（含 PoW 换 token、章节解密出正文）是强证据，应在报告中如实记录"协议级验证"；但 L2 真引擎验证（Rhino 移植后的 jsLib）仍需照跑，两者都要有。

## 与 Python 调试引擎的关系

`debugger/test_universal.py` 是**辅助调试工具**（近似引擎，可能有差异），不是交付依据。
- 用途：快速迭代、观察中间数据、验证选择器候选
- 限制：Python 近似 Rhino/JSoup 行为，与真引擎可能有差异
- 门禁：交付前必须用 `verify_source.py`（真引擎）产出报告

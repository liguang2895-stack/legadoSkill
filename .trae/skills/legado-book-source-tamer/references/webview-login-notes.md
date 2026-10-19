# WebView / WebJs / 登录态实战要点

> 来源：真机实测记录 + Legado 源码行为确认。写涉及动态渲染或登录的书源前必读。

## WebView 位置（最常见错误）

- **WebView 必须写在 `chapterUrl` 上**。Legado 只读取 `chapterUrl` 规则里的 webView 选项。
  - 正确：`"/book/{{$.id}},{\"webView\":true}"` 或 `"href##$##,{\"webView\":true}"`
  - 错误：只在 `ruleContent` 里设 webView，chapterUrl 没写 = **无效**
- **JSON API 不需要 WebView**。搜索/详情/目录走 JSON 接口的，不要在这些 URL 上加 webView——只加在 chapterUrl 上。
- 正文是 SSR 时**不要**用 webJs：HTML 里已有正文就直接 CSS 选择器（如 `#content@textNodes`）。webJs 在验证码页面空转会超时。

## webJs 写法

- **必须有轮询等待**。CSR 页面 DOM 在 JS 执行后才出现，不等待的 webJs 会拿到空内容。
- 轮询模式：`while` 循环 + `java.sleep()` 等待目标节点出现，拿到后返回。
- 返回值必须非空（`rule_audit.py` 会检查 webJs 是否含 `return`/`while`/`querySelector` 等特征）。

## 登录态标准三件套

```
enabledCookieJar: true
loginUrl: "<站点登录页 URL>"
header: "{\"Cookie\":\"<js>java.getCookie()</js>\"}"   ← 动态注入，不写死
```

- header 里**不能写死 Cookie 字符串**，必须用 `java.getCookie()` 动态取。
- 登录 Cookie 按 eTLD+1（主域）归一存储，www/wap/m 子域共享。
- 桌面浏览器登录的 Cookie 注入到手机 WebView 可能被反爬识破（UA/环境不一致）；有条件时优先在目标环境原生登录。

## VIP / 付费章节检测

`"isVip": "@js:result.outerHtml().includes('icon-lock')"` —— 防止用户点到付费章报错。
付费墙站点按 `degraded` 交付（免费章节可用），不得写 full pass。

## 反爬叠加与探测纪律

- 常见三层叠加：Cloudflare → 百度/360 验证 → Geetest 滑块。前两层 Cookie 可能过，滑块必须人工。
- **不要反复访问同一反爬入口**：连续探测会累积触发 IP 级风控，可能导致之后正常浏览器也弹验证。
- 命中验证码/Cloudflare 后：按 `verification-policy.md` 的 blocker 处理表操作，禁止换关键词/换 mode 反复重试。

## 加密正文边界

正文 API 返回 AES-GCM 密文、页面 JS 自行解密后渲染到 DOM 的站点：
- 书源**只负责从 DOM 提取**（webView + webJs 等待渲染），**不负责解密**。
- 不要分析加密算法、密钥派生或签名逻辑——那是页面 JS 的工作。

## 其他实战坑（实测记录）

- **`@css:` 多 action 链有解析 bug**：`@css:selector@action@js:...` 会触发 Legado 的 `lastIndexOf('@')` 解析问题——前面的 `@action` 被当成 CSS 选择器导致 Jsoup 报错。需要链式处理时用 `##$##<js>` 替代。
- **`:has()` / `:contains()` 不支持**：Legado 用 Jsoup，不是 jQuery。替代方案：`:has(x)` → 用父级选择器；`:contains(文本)` → `text.文本` 语法或 `@text` + `<js>` 过滤。
- **目录分页和正文分页经常同时出现**：`nextTocUrl`（目录翻页）和 `nextContentUrl`（同章翻页）两个都要检查，不要漏。
- **域名重定向要告知用户**：如 xbiquge.com → xbiquge.com.cn，不能静默切换，交付说明里写清楚。
- **`;post=` 简写语法在部分 Legado 版本不工作**（返回 404），统一用 `url,{"body":"...","method":"POST"}` 的 JSON options 写法。
- **Browser 能看到 ≠ validator 能拿到**：浏览器走真实 Chrome（有 JS/指纹），validator 走 HTTP 客户端，反爬规则不同。验证以 validator 报告为准。
- **WebView 不能绕过 Cloudflare Turnstile**：加 `webView:true` 不等于能过验证码。Turnstile 是硬边界，按 blocker 如实收敛。


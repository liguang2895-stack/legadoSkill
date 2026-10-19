# 禁止项、检查清单与特殊场景

生成书源后、交付前，逐条对照本清单。

## 一、绝对禁止

1. ❌ `prevContentUrl` 字段 —— Legado 正文只有 `nextContentUrl`。
2. ❌ `:contains(文本)` 伪类 —— 用 `text.文本` 语法，如 `"nextContentUrl": "text.下一章@href"`。
3. ❌ `:first-child` / `:last-child` —— 用位置索引 `.0`、`.-1`。
4. ❌ 不抓真实 HTML 就写规则；凭记忆/照搬别的站的选择器。
5. ❌ 编造知识库里不存在的字段和语法。
6. ❌ 正则多规则末尾多写 `##`（见 rules-spec 正则三式）。
7. ❌ GBK 站不配 `charset:"gbk"`。
8. ❌ 跳过调试直接交付。
9. ❌ **用户要"订阅源"却做书源格式** —— RssSource 字段是 `sourceName`/`sourceUrl`/`ruleArticles`/`ruleLink`，不是 `bookSourceName`/`ruleSearch`。做错整轮返工（圈圈粉案例教训）。
10. ❌ **订阅源填 `ruleDescription`** —— 填了打开文章只显示摘要文字，不加载正文（源码 `ReadRssViewModel` 行为）；要完整正文（图片/视频）就别填。详见 `rss-source-spec.md` 第七节。
11. ❌ **订阅源 `ruleImage` 返回多值** —— `.post-gallery img@src` 命中多张图时用 `\n` 拼接成非法 URL，封面空白；用 `<js>` 取首图（见 `rss-source-spec.md` 第八节）。
12. ❌ **视频帖把 `<video>` 转成文字直链** —— 应保留 `<video controls>` 并构建完整 HTML 页面，才能内嵌播放（见 `rss-source-spec.md` 第九节）。
13. ❌ **sortUrl JS 里用 `\n` 字面量拼输出** —— JSON 序列化会把 `\n` 变真实换行导致 JS 语法错误；用 `String.fromCharCode(10)`。
14. ❌ **jQuery 扩展选择器**（`:has()`/`:eq()`/`:first-of-type`）—— 静态审计直接报错；用 `<js>` 替代。
15. ❌ **硬编码页面里的 AES/签名密钥** —— 密钥可能每日轮换（藏在随机名 JS 里），书源必须**动态提取**（见 js-api.md 动态密钥一节）。硬编码的源会在换密钥当天集体失效。
16. ❌ **反爬站用 `java.get/post`** —— 它们不带书源 UA/CookieJar/重定向；一律 `java.ajax`（见 js-api.md 对比表）。
17. ❌ **form 类 POST body 带 Content-Type 头** —— Legado 会改走 postJson 以 application/json 发送，PHP `$_POST` 收不到（见 js-api.md POST 编码规则）。
18. ❌ **跨语言传拼接字符串** —— `a+b` 产生 ConsString，传给 java.* 方法报 `ClassCastException`；用 `S()`（数组 join）拍平（见 js-api.md）。
19. ❌ **假设 API 分页连续** —— 分页可能重叠（689 章书 page1=1..207/page2=99..198），合并多页必须按主键去重。
20. ❌ **兜底目录不排序** —— 详情页内嵌目录顺序是"最新章节在前 + 1-100 章块在后"；必须从 URL 提取章号排序（`-([0-9]+).html`）。
21. ❌ **`Object.prototype.toString` 补丁后不还原** —— Mock DOM 执行签名 JS 后必须 `finally { Object.prototype.toString = _toString; }`，否则污染同会话其它 JS 规则。
22. ❌ **不问就默认"都不要"直接开工** —— 用户给 URL 但没说明时，发现规则/正则净化两项需求必须先提问确认（见 SKILL.md「开工前需求门禁」），拿到答复再动手；确认要的不写=返工。
23. ❌ **签名站报 `ReferenceError: xxx 未定义` / 签名返回 `00000000` 就放弃或改 WebView** —— 这是签名站升级了指纹项（军备竞赛），按 js-api.md「指纹军备竞赛」流程补 Mock DOM（如 v16→v17 加了 navigator/createElementNS/contains）；不要上 WebView 硬渲染。
24. ❌ **修复签名时顺手动目录/正文逻辑** —— 最小改动原则：签名问题只改搜索 Mock DOM（它们互不相关）。

## 二、HTML 结构字段完整性检查清单

### 搜索页 ruleSearch
- [ ] 列表容器 bookList 定位到**重复元素**（不是其父容器）
- [ ] name、bookUrl 必填且命中
- [ ] 搜索页有无封面？无 → `coverUrl: ""`
- [ ] 作者格式：`作者：xxx` → `##^作者：`；`类别 | 作者：xxx` → 用正则拆
- [ ] 多个同名标签（如两个 `<p class="author">`）→ 索引 `.0`/`.-1` 区分
- [ ] 最新章节是否合并在其他文本里

### 详情页 ruleBookInfo
- [ ] name、author 必填
- [ ] 封面是否懒加载：`data-original` 优先，如 `img@data-original`，备选 `src`
- [ ] intro 取 `@html` 还是 `@text`（含 `<br>` 换行的用 @html 并清理标签）
- [ ] 详情页与目录是否同页 → 决定 tocUrl（见 rules-spec）

### 目录页 ruleToc
- [ ] chapterList 命中所有章节
- [ ] 有 `<select>` 分页或"下一页"链接 → nextTocUrl
- [ ] 最新章节往往排在目录最前（VIP 置顶），正文列表通常在后面——确认 bookList 没把"最新章节"块混进来，必要时用索引或正则剔除
- [ ] **API 型目录**：多页合并按章节 URL 去重（分页可能重叠）；最终按章号排序
- [ ] **兜底目录**（详情页内嵌）排序 + 去重：章号从 URL 提取，不能依赖页面顺序
- [ ] **密钥/签名是动态的**：确认是运行时提取（随机名 JS 正则）而非硬编码

### 正文页 ruleContent
- [ ] content 必填；广告段落、提示语（"本章未完…""请收藏…"）用 `##规则1|规则2` 清理
- [ ] **用户确认要净化**：净化正则必须实际命中（在正文 HTML 上跑 `rule_validator.py` 验证），交付说明写明清理了什么
- [ ] "下一章/下一页"判定 → nextContentUrl（见 rules-spec）
- [ ] 段落缩进/空行可留待阅读器排版，不必过度清洗

### 发现页 exploreUrl（整齐度检查）
- [ ] **先确认用户需求**：用户确认要发现规则才写；未确认必须先提问（见 SKILL.md「开工前需求门禁」）
- [ ] 每个分组标题带 `layout_flexBasisPercent: 1.0` 且 `url: ""`
- [ ] 两列按钮统一 `0.45`（不要 0.5）；三列 0.29；四列 0.2
- [ ] 没有 `textAlign` / `fontWeight` 等无效字段（Legado 只认 `layout_*`）
- [ ] 完整规范与黄金模板见 `references/explore-layout.md`

### 订阅源 RssSource（字段完整性 + 陷阱检查）
- [ ] 字段名是 `sourceName`/`sourceUrl`/`ruleArticles`/`ruleTitle`/`ruleLink`（不是书源字段）
- [ ] `ruleArticles`/`ruleTitle`/`ruleLink` 三件套齐全且命中
- [ ] `ruleImage` 是单值（多值会封面空白）；视频帖取 `video@poster`，图集帖取首图
- [ ] **没填 `ruleDescription`**（除非刻意只要摘要列表）
- [ ] `ruleNextPage: "page"` 与 URL 的 `{{page}}` 配套
- [ ] `searchUrl` 的 `{{key}}` 实测过（中文/英文关键词都试）
- [ ] `sortUrl` 格式为 `名::URL` 换行分隔；动态 JS 有 try/catch 降级
- [ ] 正文含 `<video controls>`（视频站）或完整 `<img>`（图集站）
- [ ] 导入格式与入口匹配：编辑界面=单对象 `{}`，文件导入=数组 `[{...}]`
- [ ] 完整规范、harness 验证法与坑表见 `references/rss-source-spec.md`

## 三、Cloudflare / 验证页处理

特征：403/502/503 状态码；页面含 "Just a moment"、"Checking your browser"、"DDoS protection"。

**先分流再动手**（详见 `encrypted-api-altcha.md` 决策树）：

- 接口 403/4001 但**页面无验证码组件** → 大概率是无感 PoW（ALTCHA 等），搜 JS 里 `captcha`/`challenge` 接口，**本地算 PoW 免人工换 token**，不要上 WebView。
- 页面含 "Just a moment" 的 CF 盾 → 下面的 loginCheckJs 半自动方案，或复刻协议直接绕开被盾页面。
- **CF 验证是按会话的**：浏览器里全程只过 1 次盾。WebView 过盾后要共享会话复用，不要每章重开 WebView（否则每章都要过盾）。
- WebView 注入页面时要带**真实 Android Chrome UA**（Legado 默认桌面 UA 会与 CF 的 Android 检测冲突导致验证失败）。

在书源 JSON 顶层加 `loginCheckJs`（半自动方案：自动重试 3 次 WebView 等待，失败弹浏览器手动过验证）：

```json
"loginCheckJs": "(function(a){var r=a.url(),o=a.body(),t=a.code();if(o&&(403===t||503===t||502===t||200===t&&(o.includes('Just a moment')||o.includes('Checking your browser')))){var c=source.get('cf_count')||'0';c=parseInt(c)+1;source.put('cf_count',c);if(c<=3){for(var i=0;i<2;i++){try{var h=java.webView(r,r,'setTimeout(function(){window.legado.getHTML(document.documentElement.outerHTML);},5000);');if(h&&!h.includes('Just a moment')&&200===java.connect(r).code()){source.put('cf_count','0');return a}}catch(e){}}}java.toast('需要CloudFlare验证');java.startBrowserAwait(r,'验证');source.put('cf_count','0');return java.connect(r)}return a})(result)"
```

- 仅在真遇到验证时加，正常站不要加（增加开销）。
- 需要账号登录的站用 `loginUrl` 字段（登录页 URL）或 `loginUi`+`loginCheckJs` 组合，参考 `js-extend-methods.md`。

## 三·五、加密 API 站专项禁止项（zjread 案例总结）

1. ❌ 接口 403 就上 WebView 硬渲染 —— 先搜 JS 找 PoW/协议，本地复刻（见 `encrypted-api-altcha.md`）。
2. ❌ 逆向 WASM 解密模块 —— 先找协议里的 `key_material`/HKDF info 字符串，本地重派生（标准算法）。
3. ❌ `bookList` 直接返回对象数组 —— 必须返回**字符串数组**（元素 `JSON.stringify`），否则 `ClassCastException: String cannot be cast to List`。
4. ❌ 在 jsLib 里直接用 `java`/`source` —— jsLib 作用域为空绑定，用 `zjInit(java,source)` 显式注入。
5. ❌ 用 `Packages.java.lang.reflect.*` —— 真机部分包被阻止，只用 `java.*` 原生方法（strToBytes/bytesToStr/hexDecodeToByteArray）。
6. ❌ Java 字符串与 JS 字面量 `===` 比较 —— 永远 false，用 `String(h).indexOf(...) >= 0`。
7. ❌ `java.base64Encode` 处理二进制 —— 按 UTF-8 损坏数据，手写 base64。
8. ❌ GCM 用 IvParameterSpec —— SunJCE 拒绝，必须 `GCMParameterSpec(128, iv)`。
9. ❌ 目录大 JSON（>200KB）硬解密 —— 超时，走 WebView 提 DOM 或精简接口。
10. ❌ 在 `java.webView` 的 js 参数里自己 setTimeout 轮询 —— 与 Legado 自动重试（约 30 次/28s）打架，写「同步单次检查，未就绪返回 null」。
11. ❌ 每章重新过一次 CF 盾 / 每章重新解验证码 —— 会话与 token 都要缓存复用（源变量，token 通常 300s）。

## 四、交付自检

- [ ] **需求门禁已过**：发现规则/正则净化两项已向用户确认（要的写了且验证命中；没要的未写）
- [ ] 输出为 JSON 数组，可直接导入
- [ ] 已保存 `{书源名}.json` 到工作目录，并归档到 `temp/<书源名>/`
- [ ] 调试引擎跑通搜索→目录→正文全链路（或明确说明失败原因）
- [ ] 已说明编码、特殊处理（懒加载/合并字段/分页/验证）
- [ ] 已提醒用户在 Legado APP 实测

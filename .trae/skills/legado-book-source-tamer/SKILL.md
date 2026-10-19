---
name: legado-book-source-tamer
description: Legado（阅读）书源/订阅源驯兽师——给网站自动编写、调试、验证 Legado 书源与订阅源 JSON。输入一个小说/漫画/博客/资源/博主站 URL，分析真实 HTML 结构，生成符合 Legado 规范的完整源（书源：搜索/详情/目录/正文；订阅源：分类导航/列表/文章/翻页），用内嵌真验证器（Kotlin 移植版规则引擎）跑通并产出验证报告。覆盖加密 API 站（bootstrap/HKDF/AES-GCM 协议复刻、章节本地解密）、每日轮换密钥/签名站（随机名 JS 动态提取、Mock DOM 执行签名）、人机验证免人工方案（ALTCHA 本地 PoW 换 captcha_token）、Cloudflare/登录态处理、视频/图集内嵌渲染、动态分类导航。当用户提到「书源」「订阅源」「RSS源」「RssSource」「Legado」「阅读APP」「阅读3.0」「写源」「bookSource」「搜索规则」「目录规则」「正文规则」「给这个网站做个源」「文章流」「博主订阅」「加密接口书源」「动态密钥」「签名」「ALTCHA」「人机验证」或提供网站 URL 要求接入阅读APP时，一律使用本技能。也覆盖源调试报错、验证失败回修、规则语法问答（CSS选择器/JSONPath/XPath/js规则）。
---

# Legado 书源/订阅源驯兽师（ZCode 版）

你是 Legado 源开发专家。任务：根据目标网站的真实 HTML，编写并验证符合 Legado（阅读 APP）规范的书源或订阅源 JSON。

**先分清做哪种源**（做错格式整轮返工）：
- **书源（BookSource）**：小说站形态「书→目录→章节正文」→ 走三阶段生成流程。
- **订阅源（RssSource）**：文章流形态（博客/资讯/资源站/博主站，首页即更新列表）→ 读 `references/rss-source-spec.md` 按订阅源规范做。
- 用户明说"订阅源"就必须做 RssSource 格式（字段是 `sourceName`/`ruleArticles`/`ruleLink` 等，**不是** `bookSourceName`/`ruleSearch`）。

技能根目录 = 本 SKILL.md 所在目录，下文以 `SKILL_DIR` 指代。

---

## 核心原则（先读再动手）

1. **一切以真实 HTML 为准**。不获取目标网站真实页面就写规则 = 必然失败。知识库和模板只提供"格式和模式"，选择器必须从真实 HTML 分析得出。
2. **验证分级，结论不能强过证据**：
   - **L1 静态审计**：`scripts/rule_audit.py`，写规则后立即跑。
   - **L2 真引擎验证**：`scripts/verify_source.py`（内嵌 Kotlin validator，Legado 规则引擎等价实现），**交付前必跑**，产出 `verify-report.json`。
   - **L3 App 实测**：最终可用性由用户在 Legado APP 导入确认，交付说明必须提醒。
   - 报告只能由脚本生成，**禁止手写或改写结论**；源文件改动后旧报告自动失效，必须重跑。
3. **Python 调试引擎是辅助**。`debugger/test_universal.py` 可快速迭代，但它是近似实现；交付依据只能是 `verify_source.py` 的报告。
4. **禁止编造规则语法**。不确定的语法先查 `references/`，再查不通就用官方源码确认。
5. **反爬纪律**：验证码/Cloudflare 命中后禁止换关键词、换 mode 反复重试（会累积 IP 风控）；桌面通过 ≠ Android 通过；SSR/CSR 判定看原始响应不看渲染后 DOM。
6. **加密 API 站先复刻协议，再考虑 WebView**：接口 403/密文/签名头时，按 `references/encrypted-api-altcha.md` 的决策树处理——优先本地 PoW 免人工验证（ALTCHA），协议跑通后四链路全走 java.get/post，快、稳、可缓存。
7. **需求门禁**：用户给 URL 要求做源、未说明时，必须先用提问工具（ZCode 下为 `AskUserQuestion`）确认①发现规则②正则净化两个需求，拿到答复再开工——禁止不问就默认"都不要"静默跳过（见「三阶段生成流程」开头的门禁）。

## 工具映射（本技能在 ZCode 中的操作方式）

| 任务 | 命令（在 SKILL_DIR/scripts 下执行） |
|------|------|
| 检测网站编码（写规则前必做，只做一次） | `python smart_fetch.py --detect <url>` |
| 抓取真实 HTML（GET/POST 均可，自动按编码解码） | `python smart_fetch.py <url> [--method POST --body "a=1&b=2"] [--header "K:V"] [--charset gbk] --save <输出.html>` |
| 智能分析网站结构（搜索表单/分页/列表） | `python smart_web_analyzer.py <url>` |
| 验证选择器/正则是否命中已保存的 HTML | `python rule_validator.py --html <page.html> --type css --rule ".box a@text"`（type 可选 css/xpath/regex；退出码 0=命中/2=未命中/1=语法错误） |
| 多模式提取试验（Default/CSS/JSONPath） | `python multi_mode_extractor.py --html <page.html> --rule <规则>` |
| **L1 静态审计（写规则后必跑）** | `python rule_audit.py <书源.json>`（退出码 0=通过/1=有 error） |
| **L2 真引擎验证（交付前必跑）** | `python verify_source.py <书源.json> -k "实测关键词"` |
| **交付前复核报告有效性** | `python verify_source.py <书源.json> --check`（源改动后报告自动失效） |
| 验证器生命周期管理（一般不用手动） | `python validator_run.py setup-jre\|start\|status\|stop` |
| 调试整个书源（近似引擎，辅助用） | `python debugger/test_universal.py <书源.json> -k "搜索词"`（退出码 0=通过/1=失败；`--auto-fix` 启发式修复） |
| 整理产物到书源专属文件夹 | `python organize_files.py --name <书源名> --files <文件1> <文件2> ...` |
| 深度查询真实书源案例库 | `python kb_query.py "关键词"`（自动搜索本机 legadoSkill 仓库 assets） |

HTML 分析本身也可直接用 Read 读已保存的 HTML 文件 + Grep 定位结构；上述脚本是快捷入口。

## 工作模式判定

- **问答模式**：用户问规则语法、字段含义（"@text 和 @html 区别？""POST 怎么配？"）→ 直接读 `references/rules-spec.md` 等参考文件作答，不创建源。
- **生成模式（书源）**：用户给小说/漫画站要求做书源 → 走下方三阶段流程（**先过开工前需求门禁**：确认发现规则/净化）。
- **生成模式（订阅源）**：用户给博客/资源/博主站要求做订阅源，或明说"订阅源/RSS" → **先读 `references/rss-source-spec.md`**，按其字段表与检查清单执行；验证用第十节的 harness 转书源技法（**开工前同样先过需求门禁**：确认分类导航/净化）。
- **调试模式**：用户给出现成源 JSON 要求修 → 先复现问题（书源跑 `verify_source.py`；订阅源按 rss-source-spec 第七~九节核对字段陷阱），定位失败环节后重写对应规则。

**特殊站点分流（第一阶段内判定，命中即读对应参考）**：

| 判定信号 | 分支 | 参考文件 |
|---------|------|---------|
| 接口 403 但页面无验证码组件 / 响应是密文 `{data,nonce}` / 有 `key_mode`、`key_material` / 全 POST 接口 | **加密 API 站**：复刻协议（bootstrap→HKDF→AES-GCM+HMAC），人机验证走 ALTCHA 本地 PoW 免人工换 token，章节内容本地重派生密钥解密 | `references/encrypted-api-altcha.md` |
| 页面含 "Just a moment" / CF 盾 / 需登录 | WebView 过盾或登录态处理（优先看能否绕开接口） | `references/webview-login-notes.md`、`references/pitfalls.md` 第三节 |
| 列表/正文靠 XHR JSON | API 发现三步法 | `references/api-discovery.md` |
| 内容 JS 动态渲染、直接抓不到 | WebView 动态加载 | `references/dynamic-loading.md` |
| 页面引用**随机名 JS**（如 `/templates/js/<32位>.js`）/ 签名函数 / API 昨天通今天 `code:-1` | **动态密钥/签名站**：密钥每日轮换，必须运行时提取（正则抓随机名 JS 里的密钥）；搜索签名用 Mock DOM 执行 signJs；反爬站一律 `java.ajax` | `references/js-api.md`（动态密钥/Mock DOM 两节）、`references/case-studies/猫扑小说-案例笔记.md` |

## 三阶段生成流程

### 开工前需求门禁（必须执行，禁止静默跳过）

用户给了 URL 要求做源时，先核对两件事；**用户未明确说明的维度，必须先问清、拿到答复再进入第一阶段**：

1. 是否需要**发现规则**（exploreUrl 首页分类导航）？
2. 是否需要**正则净化**（清理正文广告/水印）？

- 提问方式：用提问工具弹选项（ZCode 下为 `AskUserQuestion`，推荐选项：`都要` / `只要发现规则` / `只要净化` / `都不要`）；没有该工具时在回复中直接提问并**等待答复**。不要把问题只夹在正文里就直接往下做。
- 用户选了什么就写什么：**选了必须写进源、并通过验证覆盖**；没选就不写。漏写=返工。
- 若用户要了但站点确实不具备（无分类导航可做/正文无广告可清），交付说明中如实说明，不能悄悄省略。
- 只有用户**明确答复**"不需要/都不要"或授权"你看着办"时，才按"都不要"继续；❌ 禁止不问就默认"都不要"直接开工。

**发现页（exploreUrl）质量要求**：只要做发现页，必须先读 `references/explore-layout.md` 并套用其中的黄金模板。硬性规范：
- 每个分组标题：`style: {layout_flexBasisPercent: 1.0, layout_justifySelf: "center"}` + `url: ""`；
- 两列按钮：`style: {layout_flexBasisPercent: 0.45}`（**不要 0.5**，会溢出换行）；三列 0.29；四列 0.2；
- **不要写 `textAlign` / `fontWeight`**——Legado 不支持这些字段，写了无效；
- 不写 `style` 的条目宽度随文字变化，正是"发现页不整齐"的根源。
- **进阶需求**（分类很多/需要筛选器/标签长短不一）→ 读 explore-layout.md 第六~八节的现成模板：下拉框（select+infoMap）、折叠分组（▸/▾ + source.setVariable + java.refreshExplore）、等宽格子（textWidth/pack 算法，短标签 4 列长标签 3 列+空位补齐）。

### 第一阶段：收集信息（禁止输出任何 JSON！）

1. 查参考文件：读 `references/rules-spec.md`（规则语法）+ `references/templates.md`（真实模板）。**同类站先查案例库**：`python scripts/kb_query.py "<站点特征词>"`（如"加密 API""ALTCHA""懒加载 漫画"）——命中后 `--show <文件名>` 看真实成品，能少走大量弯路。
2. **检测编码**：`python scripts/smart_fetch.py --detect <url>`。记录结果，全程只用这一个编码；GBK 站后续所有请求与书源配置都要带 `charset:gbk`。
3. **抓真实页面**：搜索页（用推测的 searchUrl 带 `{{key}}` 试搜一个常见词）、详情页、目录页、正文页，各保存一份 HTML（`--save`）。POST 站必须用 `--method POST --body`。
4. **分析 HTML**：Read/Grep 已保存的 HTML，搞清楚：
   - 列表容器与重复元素；书名/作者/分类/封面/最新章节各在哪个标签
   - 搜索页有没有封面（很多站没有 → coverUrl 留空字符串）
   - 是否懒加载（`data-original` 优先于 `src`）
   - 作者信息是否合并（"科幻灵异 | 作者：钱真人" → 用正则拆分；多个同名标签用位置索引 `.0`/`.-1` 区分）
   - 目录页是否有 `<select>` 分页（→ `nextTocUrl: "option@value"`，详见 `references/rules-spec.md` 分页一节）
   - 正文有无"下一章/下一页"链接（区分章节翻页与同章分页，只有真下一章才配 `nextContentUrl`）
   - 有无 Cloudflare 特征（403/503、"Just a moment"）→ 见 `references/pitfalls.md` loginCheckJs 方案
5. API 型站点（返回 JSON）不要瞎猜接口：按 `references/api-discovery.md` 的三步法分析页面 JS 找真实 API。
6. **加密/反爬信号排查**：若接口返回 403/4001、响应是密文（`{data,nonce}`）、JS 里有 `bootstrap`/`hkdf`/`X-Signature`/`captcha`/`altcha` 字样 → 立即切 `references/encrypted-api-altcha.md`：先用 Python 复刻全协议（bootstrap→派生→签名→解密→PoW），验证通过再进第二阶段。**不要用 WebView 硬渲染代替协议复刻**。
7. 阶段产出 = 编码结论 + 各页 HTML + 结构分析笔记（加密站另加：协议复刻脚本 + 各接口明文样本）。仍然不写 JSON。

### 第二阶段：编写并审查规则

1. 基于真实 HTML 写各规则（语法全部对照 `references/rules-spec.md`）。先在已保存 HTML 上用 `rule_validator.py` / `multi_mode_extractor.py` 验证每条选择器命中，再进入下一步。
2. 逐条对照 `references/pitfalls.md` 的禁止项与检查清单（prevContentUrl、`:contains()`、`:first-child`、正则 `##` 末尾规则、nextContentUrl 判定、tocUrl 是否需要……）。
3. JSON 结构完整性：必填字段齐全（bookSourceUrl/Name、searchUrl、ruleSearch.bookList/name/bookUrl、ruleToc.chapterList/chapterName/chapterUrl、ruleContent.content），可选字段按真实 HTML 有则写。**用户确认要的两项特殊对待**：要发现规则 → 必写 exploreUrl+ruleExplore 并实测命中；要净化 → content 规则必须带清理正则并实测命中（对应用 `rule_validator.py` 在正文 HTML 上验证）。
4. **L1 静态审计门禁**：`python rule_audit.py <书源.json>` 必须通过（退出码 0），有 error 先修再继续。

### 第三阶段：创建书源

1. 组装完整 JSON（参考 `references/templates.md` 的严格模式模板）。
2. **输出两样东西**：
   - 对话中给出完整 JSON 数组（用户复制即可导入 Legado）；
   - 用 Write 保存到当前工作目录 `{书源名}.json`。
3. **L2 真引擎验证门禁**：`python scripts/verify_source.py <书源.json> -k "<实测关键词>"`。
   - `passed` → 可交付；`partial`/`degraded` → 只能按降级话术交付，明确列出未通过链路；`blocked`/`failed` → 按报告 blocker 处理（见 `references/verification-policy.md`），修到过或如实告知用户站点限制。
   - 搜索被反爬阻塞时用 `--book-url "<详情页URL>"` 跳过搜索验证后续链路。
   - 报告 `verify-report.json` 与书源一起归档；**改了书源后必须重跑**（交付前用 `--check` 复核）。
4. 整理产物：`python scripts/organize_files.py --name <书源名> --files <本次生成的 json/html/verify-report.json...>`，归档到 `temp/<书源名>/`。
5. 交付说明必须包含：验证等级与报告状态（引用 `verify-report.json` 的 `status`/`phases`/`blocker`）、编码、特殊处理（懒加载/合并字段/分页/验证）、**发现规则与净化需求的处理结论**（用户要了=已写并验证；没要=未写）、以及"请在 Legado APP 实测"。
   - **禁止**：手写报告结论、把局部成功写成全链路可用、未验证却声称可用。

## 订阅源生成流程（RssSource）

> 详细规范与坑表见 `references/rss-source-spec.md`。以下是精简流程。

1. **判定**：文章流形态（首页=更新列表）→ 订阅源。用户明说"订阅源"一律照做。**需求门禁**：用户未说明时，先问清是否需要分类导航（sortUrl）与正文净化。
2. **收集**：抓列表页 HTML（首页/分类页）+ 文章页 HTML；确认标题/时间/封面/链接/正文各在哪；视频帖看 `video@poster`、图集帖看首图。
3. **写规则**（字段名全是 `sourceXxx`/`ruleXxx`，不要混入书源字段）：
   - `sortUrl`：`分类名::URL` 换行分隔；静态优先，动态才用 `<js>`（`java.ajax` 拉数据 + try/catch 降级）。**用户确认要分类导航才写**。
   - `ruleArticles` + `ruleTitle` + `ruleLink`：三件套必填。
   - `ruleImage`：**必须单值**（多值会封面空白）→ 用 `<js>` 取首图。
   - **不填 `ruleDescription`**（填了打开文章只显示摘要，不加载正文——源码行为）。
   - `ruleContent`：构建完整 HTML 页面；视频保留 `<video controls>` 内嵌播放。**用户确认要净化 → 在这里加清理正则/JS 替换并实测命中**。
   - `ruleNextPage: "page"` + URL 带 `{{page}}`。
   - `searchUrl`：`...?s={{key}}` 之类，实测中文/英文关键词。
4. **验证**（无订阅源验证器）：
   - 把规则转书源 harness 跑 `verify_source.py`（见 rss-source-spec 第十节），验证列表命中/字段提取/正文构建；
   - Python 脚本模拟 `RssParserByRule` 流程补充验证；
   - 用 Node `eval` 单独跑 sortUrl JS 确认输出行数与格式。
5. **交付**：确认导入方式（编辑界面=单对象 `{}`；文件导入=数组 `[{...}]`），附完整 JSON + 文件 + 提醒 App 实测。

## 规则速记（详见 references/rules-spec.md）

- 规则四段式：`选择器@提取类型##正则##替换`。提取类型：`@text @ownText @html @href @src @content`；位置索引 `.0 .-1`；属性 `@href/@src/@value`。
- 正则三式：删除 `##规则1|规则2`（末尾**不写**##）；替换 `##规则##新内容`；提取 `##.*作者：(.*)##$1`。
- **两段式规则**：`属性名\n@js:...` —— jsoup 先提属性（自动解码 `&amp;`），JS 拿干净值（onclick 藏 URL 必用）。
- POST：`URL,{"method":"POST","body":"k={{key}}&p={{page}}","charset":"gbk"}`；UTF-8 站省略 charset。
  - **form body 不写 Content-Type 头**（写了 Legado 会当 JSON 发）；options 里不要嵌套 headers（validator 解析不了）。
- 反爬站用 `java.ajax`（自动带书源 UA/Cookie/重定向），不用 `java.get/post`。
- 禁止：`prevContentUrl` 字段、`:contains()`、`:first-child/:last-child`（用 `text.下一章` 和数字索引替代）、硬编码每日轮换的密钥。

## 参考文件路由（按需读取，不要一次全读）

| 场景 | 读这个 |
|------|--------|
| 写任何规则前 | `references/rules-spec.md`（Default/CSS/XPath/JSONPath 语法、分页、nextContentUrl/tocUrl、**两段式规则 `属性名\n@js:`**） |
| **做订阅源（RssSource）时（必读）** | `references/rss-source-spec.md`（字段全表、三大解析路径、ruleDescription 陷阱、sortUrl 动态分类、harness 验证法、12 条坑表） |
| **写 exploreUrl 发现页时（必读）** | `references/explore-layout.md`（FlexChildStyle 真实字段、两列 0.45 黄金值、黄金模板、反面清单） |
| 组装 JSON / 输出前 | `references/templates.md`（5 个真实模板 + 严格输出模板 + 订阅源模板） |
| **验证与交付 / 遇到 blocker / validator 误报** | `references/verification-policy.md`（验证分级、报告契约、blocker 处理表、**validator 已知误报识别**、**Rhino 规则级验证台**、回修动作、反爬纪律） |
| 提交前自查 | `references/pitfalls.md`（禁止项 22 条、字段完整性清单、Cloudflare/登录） |
| 静态审计规则清单 | `references/official-rule-pack.json`（rule_audit.py 的检查规则来源） |
| GBK/乱码问题 | `references/encoding.md`（检测流程与配置；更深见 `references/encoding-guide.md`） |
| **需要写 JS 规则 / 反爬签名 / 加密 / API 型目录** | `references/js-api.md`（**java.ajax vs get/post 对比**、**POST body 编码规则**、**ConsString 坑**、**Mock DOM 执行签名 JS**、**动态密钥提取**、**分页重叠去重**、java.* 全量方法；扩展类详见 `references/js-extend-methods.md`） |
| **加密 API 站 / 接口 403 无验证码 / 密文响应 / ALTCHA PoW 免人工验证** | `references/encrypted-api-altcha.md`（决策树、ALTCHA 本地求解、bootstrap→HKDF→AES-GCM+HMAC 协议复刻、章节本地解密、bootstrap 携参、字段预取、错误分流、Rhino 坑表） |
| **webView/webJs/登录态站点** | `references/webview-login-notes.md`（webView 必须写在 chapterUrl、webJs 轮询、登录三件套、反爬叠加） |
| JSON 接口站 | `references/api-discovery.md` |
| 正文/目录怎么都抓不全 | `references/dynamic-loading.md`（webView 动态加载） |
| 想系统学习语法 | `references/book-source-tutorial.md`（长文教程）、`references/css-selectors-full.txt`（CSS 手册） |
| **rrssk 系合作站 / 签名搜索 / 每日换密钥 API** | `references/case-studies/猫扑小说-案例笔记.md`（搜索三步链、两段式规则、动态密钥提取、分页去重、validator 误报、Rhino 验证台实测数据） |
| 更多同类站的真实案例 | `python scripts/kb_query.py "关键词"` 搜索案例库（晋江/番茄/笔趣阁/漫画/聚合源/**加密API（zjread 纸间）**等） |

## 知识库深度查询（kb_query.py）

本技能自带的 references 覆盖常用场景。遇到罕见站点类型（有声、漫画 raw、聚合、需要登录头、**加密 API 站**等），用知识库脚本搜真实案例：

```bash
python scripts/kb_query.py "漫画 懒加载"        # 关键词检索
python scripts/kb_query.py "加密 API ALTCHA"    # 加密协议 + 免人工验证案例（zjread 纸间）
python scripts/kb_query.py --list               # 列出全部案例
python scripts/kb_query.py --show <文件名>      # 展示某个案例全文
```

**加密 API 站推荐先看**：`--show zjread技术笔记.md`（协议复刻全流程 + 踩坑）+ `--show zjread.json参考.txt`（可用的成品书源 + 技术标注）。

案例库根目录按顺序自动发现：环境变量 `LEGADO_KB_ROOT` → 技能目录旁的 `legadoSkill` 仓库 → 当前工作区的 `legadoSkill/`。若都不存在，提示用户 `git clone https://github.com/liguang2895-stack/legadoSkill.git`（脚本会打印该命令）。

知识库仅作参考：里面的选择器不能照抄，必须在目标站真实 HTML 上重新验证。

## 本技能内置案例（references/case-studies/）

| 案例 | 类型 | 看什么 |
|------|------|--------|
| `圈圈粉订阅源.json` + `圈圈粉-案例笔记.md` | 订阅源（WordPress 博主站） | 完整成品 + 迭代史（格式误判/ruleDescription 陷阱/封面多值/视频内嵌/转义坑） |
| `猫扑小说.json` + `猫扑小说-案例笔记.md` | 书源（rrssk 合作站：签名搜索 + 每日换密钥 API + GoEdge WAF） | 搜索三步链 + Mock DOM 签名、两段式属性规则、动态密钥提取、分页重叠去重、兜底排序、validator 误报识别、Rhino 验证台实测数据 |

## 工具补充：Rhino 规则级验证台（validator 误报/受限时的替代证据）

validator 对某些站点有**系统性误报**（如页面自带纠错举报表单 `<div class="captcha">` 触发 toc 阶段 CAPTCHA 误报），
此时用 validator JAR 自带的**真 Rhino 引擎**直接验证单条规则：

```bash
# 1. 从书源 JSON 提取规则 JS 到文件（如 toc_rule.js，即 "@js:" 后面的部分）
# 2. 跑验证台（page.html 可选，作为 result 初始值；baseUrl 可选）
java -cp validator/app/legado-source-validator.jar \
     org.mozilla.javascript.tools.shell.Main scripts/rhino_harness.js toc_rule.js detail.html
# 输出 HARNESS_RESULT:... 为规则返回值（可断言章节数/顺序）
```

- 详细说明与误报识别方法见 `references/verification-policy.md`"validator 已知误报"与"规则级真引擎验证台"两节。
- 注意：该验证是 L2 的补充证据（报告标注"validator 误报，Rhino 规则级验证通过"），**不能替代 L3 App 实测**。

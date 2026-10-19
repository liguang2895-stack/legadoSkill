# Legado 书源规则规范（语法权威速查）

> 来源：legadoSkill 知识库。选择器必须基于目标站真实 HTML 编写，本文只定格式。

## 规则四段式

```
选择器@提取类型##正则表达式##替换内容
```

- 每段可省略：`选择器@提取类型`、`选择器@提取类型##正则`、`@css:选择器@text` 等。
- 规则开头加前缀可切换解析器：`@CSS:`、`@XPath:`（或 `//` 开头）、`$.`（JSONPath）、`@js:`（JS 代码）。不加前缀为 Default 混合语法。

## Default 语法（jsoup 简写）

| 完整写法 | 简写 | 说明 |
|----------|------|------|
| `class.名字@text` | `.名字@text` | 类选择器 |
| `class.a.b@text` | `.a.b@text` | 多类 |
| `id.xxx@text` | `#xxx@text` | ID（优先用，最稳） |
| `class.xxx@li@a@text` | `.xxx li a@text`（可混用空格层级） | 层级 |
| `tag.a.0@text` | — | 第 0 个 a 标签 |
| `tag.span.-1@text` | — | 倒数第一个 span |
| `text.下一章@href` | — | 按文本找元素（**替代 :contains()**） |

## 提取类型

| 类型 | 说明 |
|------|------|
| `@text` | 所有文本（含子标签内文本） |
| `@ownText` | 仅自身直接文本 |
| `@textNodes` | 所有子文本节点拼接 |
| `@html` | 内部 HTML |
| `@all` | 整个元素 outerHTML |
| `@href` / `@src` / `@value` / `@content` | 取对应属性 |
| `@js:` 开头 | 该元素上执行 JS |

## 位置索引

`.0` 第一个，`.1` 第二个，`.-1` 倒数第一，`.-2` 倒数第二，`.[0:5]` 区间。
（**禁止**用 `:first-child`/`:last-child`，用索引替代。）

## 两段式规则：`属性名\n@js:...`（提取属性后跑 JS，★ 实体转义克星）

`@js:` 段收到的 `result` 是**元素 outerHTML**，里面 `&` 已转义为 `&amp;`——直接正则匹配 URL 参数会失败。
**技巧**：规则第一段写**属性名**（如 `onclick`、`data-url`），让 jsoup 先提取属性（**自动解码 HTML 实体**），
第二段 `@js:` 对干净字符串跑 JS。两段用换行 `\n` 分隔：

```json
"bookUrl": "onclick\n@js:var m=String(result).match(/[?&]t=([^&]+)&s=/);var url='';if(m){url=String(java.base64Decode(decodeURIComponent(m[1])));}url"
```

- 原理：`AnalyzeByJSoup` 的 else 分支对任意字符串执行 `element.attr(lastRule)`——`attr()` 返回时已解码实体。
- 适用：`onclick` 里藏跳转 URL、`data-*` 里藏 JSON、任何"属性值需要二次解析"的场景。
- 对比：`@js:` 单段拿 `result` 是 outerHTML（带转义）；两段式拿的是干净属性值。

**HTML 实体转义陷阱**：任何在 JS 里对 `String(result)`（outerHTML）做 URL 参数正则匹配的规则，
都要同时兼容 `&` 和 `&amp;`（`(?:&amp;|&)`），或用两段式规则绕过。

## 正则三式（`##` 分隔）

```js
"author": ".author@text##^作者："                    // 删除：末尾不写 ##，替换为空白
"content": ".content@html##规则1|规则2|规则3"        // 多规则用 | 分隔，末尾同样不写 ##
"content": ".content@text##\\s+## "                 // 替换：##正则##新内容
"author": ".author@text##.*作者：(.*)##$1"          // 提取：捕获组 + $1
```

**易错点**：
- `##规则1|规则2##` ❌ —— 末尾多写的 `##` 会把整个 `规则1|规则2` 当作被匹配串、空串作替换，语义完全变了。删除一律末尾不带 `##`。
- 捕获组后必须写 `##$1`，只写 `##` ❌。
- JS 字符串里正则的反斜杠要转义：`"##<div id=\\"tip\\">[\\\\s\\\\S]*?</div>"`（JSON 中 `\\s`，规则串里 `\s`）。

## 书源 JSON 结构（严格模式）

必填骨架：

```json
[
  {
    "bookSourceUrl": "https://example.com",
    "bookSourceName": "示例源",
    "bookSourceType": 0,
    "bookSourceGroup": "",
    "searchUrl": "/search.php?q={{key}}",
    "ruleSearch": { "bookList": "", "name": "", "bookUrl": "" },
    "ruleBookInfo": { "name": "", "author": "" },
    "ruleToc": { "chapterList": "", "chapterName": "", "chapterUrl": "" },
    "ruleContent": { "content": "" },
    "lastUpdateTime": 0,
    "customOrder": 0,
    "enabled": true,
    "enabledExplore": false
  }
]
```

- 输出必须是 **JSON 数组**。
- `bookSourceType`：0=文本，1=音频，2=图片（漫画），3=文件（RSS 类用 other 也可）。
- 搜索变量：`{{key}}` 搜索词、`{{page}}` 页码（第 1 页时 page=1；很多站首页是 1，翻页从 2 起，可用 `{{page-1}}` 或 JS 处理）。

### ruleSearch / ruleBookInfo 字段

`name`、`bookUrl` 必填；`author`、`kind`（分类）、`lastChapter`、`intro`、`coverUrl`、`wordCount` 按真实 HTML 有则写。搜索页无封面时 `coverUrl: ""`。

### tocUrl：详情页与目录页是否同一页

- 点击搜索结果进入的页面**已显示章节列表** → 不写 `tocUrl`。
- 需要点"开始阅读/全文阅读/查看目录"跳转 → `ruleBookInfo.tocUrl` 指向该链接（如 `"tocUrl": "text.查看目录@href"`）。

### ruleToc 与目录分页

```json
{
  "chapterList": "#list dd a 或 .ml_list li",
  "chapterName": "text 或 a@text",
  "chapterUrl": "a@href",
  "nextTocUrl": "option@value"
}
```

目录分页两种形态：
- `<select onchange="..."><option value="/book/1_2.html">2</option></select>` → `nextTocUrl: "option@value"`。
- "下一页/下一页»" 链接 → `nextTocUrl: "text.下一页@href"` 或对应 a 标签。
- 无分页不写 nextTocUrl。章节倒序网站（章节列表倒着排）可加 `"chapterList"` 上配正则或使用 `sortUrl`（详见教程文档）。

### ruleContent 与 nextContentUrl

```json
{
  "content": "#chaptercontent@html##<div id=\\"tip\\">[\\s\\S]*?</div>|本章未完点击下一页.*",
  "nextContentUrl": "text.下一章@href"
}
```

判定规则（重要）：
- 链接文本是"下一章 / 下章 / 下一节" → **设置** `nextContentUrl`。
- 链接文本是"下一页 / 继续阅读"且目标仍是**同一章**（分页正文） → 也设置 `nextContentUrl`（Legado 会自动拼接正文）。指向下一章的分页同章均可配，关键是 URL 能取回内容。
- 无法确定时看链接 href 是否仍指向本章（如 `/1_2.html` vs 下一章 id）。
- **Legado 没有 `prevContentUrl` 字段，永远不要写。**
- `sourceRegex`、`webJs` 属于进阶，见 `references/js-api.md`。

## searchUrl 规范

- GET：`/search.php?q={{key}}&p={{page}}`（相对路径自动拼接 bookSourceUrl 域名）。
- POST：`/search.php,{"method":"POST","body":"searchkey={{key}}&searchtype=all","charset":"gbk"}`。
  - body 必须是 String；变量用 `String(key)` 强转的写法放在 `@js:` 复杂模式里。
  - UTF-8 站省略 charset；GBK 站必须写 `"charset":"gbk"`，中文关键词还需 `java.encodeURI(key,'GBK')` 场景见 js-api。
  - ⚠️ **form 类 body 不要写 Content-Type 头**——Legado 见到 Content-Type 会改走 postJson（application/json 发送），PHP `$_POST` 收不到；让 Legado 自动 form 编码（见 js-api.md POST 编码规则）。
- 复杂请求头/动态 body 用 `@js:` 返回 `"url," + JSON.stringify(option)`：

```js
@js:
var headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://example.com"};
var body = "keyword=" + String(key) + "&page=" + String(page);
var option = {"charset": "utf-8", "method": "POST", "body": String(body), "headers": headers};
"https://www.example.com/search," + JSON.stringify(option)
```

- ⚠️ **反爬站（WAF/UA 校验/需 Cookie/302）用 `java.ajax` 而不是 java.get/post**——`java.ajax` 自动注入书源 header（UA）+ CookieJar + 跟随重定向；`java.get/post` 是 Jsoup 直连裸奔（见 js-api.md 对比表）。
- ⚠️ **签名/加密站**：`@js:` 里字符串拼接后传给 java.* 前必须用 `S()`（数组 join）拍平，否则 ConsString 报 ClassCastException（见 js-api.md）。

## exploreUrl 发现规则（仅当用户确认需要时编写）

> ⚠️ 是否编写由用户决定：用户给了 URL 但未说明时，**必须先提问确认**（见 SKILL.md「开工前需求门禁」），得到答复再动手；❌ 禁止不问就默认不写。用户确认要 → 本节规则必写并实测命中。

URL 格式必须照抄网站导航真实链接，只把页码换成 `{{page}}`：

```
分类名::/sort/1_{{page}}/\n玄幻::/sort/2_{{page}}.html
```

- 保持原后缀（`/` 或 `.html`）不变；只有一页内容的分类不加 `{{page}}`。
- `ruleExplore` 结构与 ruleSearch 相同。
- **布局整齐度**：每个条目必须带 `style.layout_flexBasisPercent`（两列 0.45 / 三列 0.29 / 四列 0.2），分组标题用 `1.0`；不要写 `textAlign`/`fontWeight`（无效字段）。完整规范、黄金模板与反面清单见 **`references/explore-layout.md`**。

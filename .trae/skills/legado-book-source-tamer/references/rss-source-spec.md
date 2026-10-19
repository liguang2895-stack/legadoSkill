# Legado 订阅源（RssSource）规范与实战指南

> 来源：官方源码 `RssSource.kt` / `RssParserByRule.kt` / `Rss.kt` / `ReadRssViewModel.kt` 逐字段核对 + 圈圈粉（WordPress 博主站）实战全链路验证。
> 订阅源 = 文章流形态（网站更新列表 → 文章），**不是** 书源的"书→章"形态。资源站/博客/资讯站/图集站/视频站一律优先考虑订阅源。

## 一、何时做订阅源，何时做书源

| 站点形态 | 选什么 | 判断依据 |
|---------|--------|---------|
| 小说站（书→章→正文） | 书源 | 有书籍详情页、目录页 |
| **博客/资讯/资源站（文章流）** | **订阅源** | 首页就是更新列表，点进去是文章 |
| **博主站（一人多帖）** | **订阅源** | 每人一个 tag 页/主页，帖子按时间排 |
| 漫画/图集站 | 书源（type=2）或订阅源 | 有连续章节结构 → 书源；纯图集流 → 订阅源 |
| 视频站 | 订阅源（type=1/2） | 列表+播放页，可内嵌 video |

**教训（圈圈粉案例）**：用户说"制作订阅源"时**必须做 RssSource 格式**，不要先做书源。两者 JSON 结构完全不同（见第三节），做错格式整轮返工。

## 二、订阅源字段全表（官方源码 `RssSource.kt`）

### 基本字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `sourceName` | String | 必填，源名称 |
| `sourceUrl` | String | 必填，唯一标识（**注意：不是 bookSourceUrl！**） |
| `sourceIcon` | String | 图标 URL |
| `sourceGroup` | String | 分组 |
| `sourceComment` | String | 注释 |
| `enabled` | Bool | 是否启用 |
| `enableJs` | Bool | 启用 JS |
| `enabledCookieJar` | Bool | Cookie 管理 |
| `loadWithBaseUrl` | Bool | 加载地址 |
| `preload` | Bool | 预加载 |
| `singleUrl` | Bool | 单 URL 源 |
| `type` | Int | 0网页 / 1图片 / 2视频 |
| `articleStyle` | Int | 列表样式：0默认 / 1大图 / 2双列 / 3瀑布 / 4三列 |
| `header` | String | 请求头 JSON 字符串 |
| `sortUrl` | String | 分类 URL（见第四节） |
| `searchUrl` | String | 搜索 URL（见第六节） |
| `customOrder` / `lastUpdateTime` | Int/Long | 排序字段 |

### 规则字段

| 字段 | 说明 | 结果类型 |
|------|------|---------|
| `ruleArticles` | 列表规则（重复元素） | List\<Element\> |
| `ruleNextPage` | 翻页规则（见第五节） | String |
| `ruleTitle` | 标题 | String |
| `rulePubDate` | 发布时间 | String |
| `ruleDescription` | **描述（高危字段！见第七节）** | String |
| `ruleImage` | 图片（封面） | String |
| `ruleLink` | 文章链接 | String（URL） |
| `ruleContent` | 正文（构建 HTML 页面） | String |
| `style` | 正文 WebView 样式（CSS 文本） | String |
| `injectJs` / `preloadJs` | WebView 注入 JS | String |
| `contentWhitelist` / `contentBlacklist` | WebView 链接白/黑名单 | String |

## 三、三大解析路径（官方源码 `RssParserByRule.kt`）

```
访问 sortUrl → 检查 ruleArticles
  ├─ 为空 → 按标准 RSS 解析（RssParserDefault，XML 解析）
  └─ 非空 → 用规则解析（RssParserByRule）：
      1. ruleArticles 提取条目列表
      2. 每条独立解析 ruleTitle / rulePubDate / ruleImage / ruleLink
      3. 检查 ruleDescription：
         ├─ 存在 → 解析描述，结束（⚠️ 打开文章只显示描述，不加载正文！）
         └─ 不存在 → 检查 ruleContent → 加载正文
```

**必填组合**（有列表规则的源）：
- `sourceName` + `sourceUrl` + `ruleArticles` + `ruleTitle` + `ruleLink` —— 缺一不可。

## 四、sortUrl 分类导航

> ⚠️ **需求门禁**：用户给了 URL 但未说明时，先提问确认是否需要分类导航（同 SKILL.md「开工前需求门禁」）；用户确认要才写本节规则，并确保 `sortUrl` 在 App 里真实渲染出分类。

### 格式

```
分类名::URL
分类名2::URL2
```

- 用 `\n`（真实换行）分隔多条；也支持 `&&` 分隔。
- URL 里带 `{{page}}` 时，翻页由框架替换页码。
- 仅一个分类时可不写 sortUrl（默认用 sourceUrl）。

### 动态分类（JS 生成）

`sortUrl` 以 `<js>` 或 `@js:` 开头时，JS 的**返回值**（字符串）被解析为分类列表。执行环境提供：`java`（可 `java.ajax()` 发请求）、`source`、`cookie`、`cache`。

```js
<js>
var out = [];
var HOST = "https://www.example.com";
// 静态分类
var cats = [["最新", "/page/{{page}}"], ["分类A", "/catA/page/{{page}}"]];
for (var i = 0; i < cats.length; i++) {
  out.push(cats[i][0] + "::" + HOST + cats[i][1]);
}
// 动态追加（如热门标签，API 拉取）
try {
  var res = java.ajax(HOST + "/api/tags?hot=1");
  var tags = JSON.parse(String(res));
  for (var j = 0; j < tags.length; j++) {
    out.push("👤" + tags[j].name + "::" + tags[j].link + "page/{{page}}");
  }
} catch (e) {}  // 失败时降级为仅静态分类
out.join(String.fromCharCode(10));  // ⚠️ 换行必须用 fromCharCode，见坑表
</js>
```

**注意**：
- JS 结果会被 Legado **缓存**（ACache，key = md5(sourceUrl + sortUrl)）；想刷新需重导入或清除缓存。
- 动态分类失败要 try/catch 降级，不能整个导航空白。
- 标签太多时建议截断（如 per_page=30），避免导航过长。

## 五、ruleNextPage 翻页

| 写法 | 语义 |
|------|------|
| `"page"`（不分大小写） | **页码自增**：URL 模板里的 `{{page}}` 由框架递增（推荐） |
| CSS/JS 规则 | 提取"下一页"链接的 href |

**`"page"` 模式**要求 sortUrl/searchUrl 里带 `{{page}}`：
- `https://site.com/page/{{page}}` ✅
- `https://site.com/cat/page/{{page}}` ✅
- `https://site.com/list?p={{page}}` ✅

**URL 形态兼容性**（实战验证）：
- 列表页 `page/1` 与无 page 的首页内容一致（WordPress 等），第 1 页 URL 直接可用。

## 六、searchUrl 搜索

- `{{key}}` = 搜索词（框架自动 URL 编码，中文无需手动处理）。
- `{{page}}` = 页码（与 ruleNextPage 配合）。
- 例：`https://www.example.com/page/{{page}}?s={{key}}`（WordPress 站内搜索）。
- 搜索与分类共用同一套 `ruleArticles` 等规则（结构通常一致）。

**搜博主/作者的两种方案**：
1. **搜帖子**（简单）：`?s={{key}}` 搜帖子标题，标题含博主名 → 出该博主全部帖子。适合博主名出现在帖子标题里的站。
2. **搜标签**（精准）：若站有标签 API（如 `/wp-json/wp/v2/tags?search={{key}}`），可返回博主列表。但订阅源搜索结果是文章流，此方案需配合列表规则适配，较复杂。

## 七、⚠️ ruleDescription 高危陷阱（本次最大坑）

**官方源码逻辑**（`ReadRssViewModel.kt`）：

```kotlin
if (!article.description.isNullOrBlank()) {
    contentLiveData.postValue(article.description!!)   // 只显示描述！
} else {
    loadContent(article, ruleContent)                   // 才加载正文
}
```

**后果**：填了 `ruleDescription` 后，打开文章**只显示列表页的摘要文字**，图片/视频/正文都不出现；用户手动点右上角刷新才强制加载正文（走 `loadContent`）。

**决策**：
- 正文需要完整渲染（图片/视频/富文本）→ **不要填 `ruleDescription`**。
- 只需要纯文字摘要列表 → 才填。
- 中间方案：`ruleDescription` 填了但保证它等于正文摘要意义不大，直接用方案一。

## 八、ruleImage 封面：多值陷阱

`ruleImage` 是**单值字段**（String），但 CSS 选择器可能命中多个元素：

- `.post-gallery img@src` 命中 23 张图 → 多值用 `\n` 拼接 → 非法 URL → **封面空白**。
- 视频帖的封面在 `video@poster`，图片帖在首张 `img@src`。

**正确写法**（用 `<js>` 取单值）：

```js
<js>
var v = String(java.getString('video@poster') || '');
if (v) { result = v; }
else {
  var l = java.getStringList('.post-gallery img@src');
  result = (l && l.size() > 0) ? String(l.get(0)) : '';
}
</js>
```

**注意**：
- `img:first-of-type` / `img:eq(0)` 等 jQuery 扩展选择器被静态审计禁止（Legado Jsoup 不支持）。
- 位置索引 `.0`（Default 语法）在部分场景下真引擎不生效，`<js>` 最稳。

## 九、ruleContent 正文：构建完整 HTML 页面

> ⚠️ **净化需求**：用户确认要净化才加清理逻辑；未确认先提问。加了净化必须实测命中（正文里确实清掉了目标广告/水印）。

订阅源的 `ruleContent` 返回值被当作 **WebView 页面 HTML** 渲染。两种风格：

### 风格 A：保留原页面结构（简单）

```js
<js>var h=String(java.getString('.post-body@html')||'');h=h.replace(/广告正则/g,'');result='<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:12px;font-size:16px;line-height:1.8;background:#0f0f12;color:#f2ead9}img{max-width:100%;height:auto;display:block;margin:8px auto;border-radius:6px}video{width:100%;max-height:80vh;display:block;margin:8px auto;background:#000;border-radius:8px}</style></head><body>'+h+'</body></html>';</js>
```

### 风格 B：完整播放器页面（视频站，参考黄果剧场）

- 用 `@js:` 构建带 `<video controls>` + hls.js 的完整页面（详见知识库案例 `黄果剧场`）。
- 适用 HLS/m3u8 流媒体站点。

### 视频内嵌播放三要素

1. **保留 `<video controls>` 标签**（不要转成"封面图+文字直链"）。
2. **构建完整 HTML**（DOCTYPE + charset + viewport + style）。
3. **CDN 需支持 CORS**：先 `curl -sI -H "Origin: <站点>" <视频URL>` 看 `Access-Control-Allow-Origin`。有 `*` 或无 CORS 限制即可内嵌。

## 十、验证方法：harness 转书源验证（本次实战技法）

**问题**：`verify_source.py` 只支持书源四链路，**不支持订阅源格式**。

**解法**：把订阅源规则**转成书源 harness**，用真引擎验证单条规则：

```python
# 把订阅源字段映射到书源字段
harness = [{
    "bookSourceName": "harness",
    "bookSourceUrl": "https://www.example.com",
    "bookSourceType": 0,
    "searchUrl": "/page/1",              # 固定列表页
    "ruleSearch": {
        "bookList": sub['ruleArticles'],  # 订阅源字段直接复用
        "name": sub['ruleTitle'],
        "bookUrl": sub['ruleLink'],
        "coverUrl": sub['ruleImage']      # <js> 规则同样有效
    },
    "ruleBookInfo": {"name": "h1@text"},
    "ruleToc": {"chapterList": "article", "chapterName": "a@text", "chapterUrl": "a@href"},
    "ruleContent": {"content": sub['ruleContent']},
    "enabled": True, "enabledExplore": False
}]
```

然后 `python verify_source.py harness.json -k "关键词"`。

**能验证的**：ruleArticles 命中数、ruleTitle/ruleLink/ruleImage 提取值、ruleContent 构建结果。
**不能验证的**：ruleNextPage 的 "page" 语义（框架行为）、sortUrl、ruleDescription 陷阱（框架行为）。
**补充验证**：用 Python 脚本模拟 `RssParserByRule` 流程（requests + BeautifulSoup）逐条检查。

**⚠️ validator 的 JS 语法差异**：
- validator 只认 `<js>...</js>` 标签，**不认 `@js:` 前缀**（真机 Legado 两者都认）。
- 写规则用 `<js>` 兼容两者。
- validator 不支持 `ruleArticles` 返回对象数组（`[{name,url}]`）的写法，真机支持；需要时用 CSS 选择器 + 独立字段规则。

## 十一、交付检查清单

- [ ] JSON 是**单对象** `{...}`（编辑界面导入）还是**数组** `[{...}]`（文件导入）——问清导入方式！
  - 编辑界面 `{}` 图标导入 → 源码 `GSON.fromJsonObject<RssSource>` → **单对象**
  - 订阅页"导入订阅源"文件导入 → `GSON.fromJsonArray<RssSource>` → **数组**
- [ ] `sourceUrl` 字段名正确（不是 `bookSourceUrl`）
- [ ] `ruleArticles`/`ruleTitle`/`ruleLink` 三件套齐全
- [ ] `ruleDescription` 已按第七节决策（要正文就别填）
- [ ] `ruleImage` 是单值（多值会封面空白）
- [ ] `ruleNextPage` 与 URL 的 `{{page}}` 配套
- [ ] `searchUrl` 的 `{{key}}` 已实测（中文/英文关键词都试）
- [ ] 正文含 `<video controls>`（视频站）或完整 `<img>`（图集站）
- [ ] harness 真引擎验证通过（第十节）
- [ ] 提醒用户：App 实测；订阅源规则改动后重导入（sortUrl JS 结果有缓存）

## 十二、坑表（实战踩过的）

| # | 坑 | 现象 | 解法 |
|---|-----|------|------|
| 1 | 导入格式错误 | `Expected BEGIN_OBJECT but was BEGIN_ARRAY` | 编辑界面导入用**单对象**；文件导入用数组 |
| 2 | ruleDescription 陷阱 | 打开文章只有摘要文字，刷新才出正文 | 删掉 `ruleDescription` |
| 3 | ruleImage 多值 | 图片帖封面空白（视频帖正常） | `<js>` 取首图（见第八节） |
| 4 | 视频不能播 | 正文显示"视频直链：https://..."文字 | 保留 `<video controls>` + 完整 HTML 页面 |
| 5 | sortUrl JS 换行 | JS 语法错误，导航空白 | 换行用 `String.fromCharCode(10)`，不用 `\n` 字面量 |
| 6 | sortUrl 缓存 | 改了分类不生效 | 结果被 ACache 缓存，重导入源或清缓存 |
| 7 | `@js:` vs `<js>` | validator 报 `SelectorParseException` | 统一用 `<js>` 标签 |
| 8 | jQuery 选择器 | 静态审计 `forbid_token` 报错 | 不用 `:has()`/`:eq()`/`:first-of-type`，用 `<js>` 替代 |
| 9 | 正文净化残留 | 老帖有"圈子：#xxx"等元信息 | 正则链多清理几条（`h.replace(/<p[^>]*>圈子：[^<]*<\/p>/g,'')`） |
| 10 | CDN 防盗链 | 视频/图片加载失败 | 检查 `Access-Control-Allow-Origin`；必要时给媒体 URL 拼 header JSON |
| 11 | `{{page}}` 从 1 开始 | 首页 URL 404 | 大多数 WordPress 站 `page/1` = 首页，实测确认 |

## 十三、圈圈粉案例速览（WordPress 博主站）

完整成品 + 迭代史参考 `case-studies/圈圈粉订阅源.json` 与 `case-studies/圈圈粉-案例笔记.md`。关键规则：

```
sortUrl:     11 个静态分类（/page/{{page}} 与 /{cat}/page/{{page}}）
searchUrl:   https://www.quanquanfen.com/page/{{page}}?s={{key}}
ruleArticles: article.post-card:not(.post-sticky)
ruleTitle:   .post-title a@text
rulePubDate: .post-meta .meta-item.0@text
ruleImage:   <js>视频取 poster，图片取首图</js>
ruleLink:    .post-title a@href
ruleNextPage: page
ruleContent: <js>净化推广文案 + 构建深色主题 HTML 页面（video 内嵌播放）</js>
```

**站点特征**：WordPress 7.x + 主题 wp-theme-aituse；帖子 = 图集（多 `<figure>`）或视频（`<video poster>`）；老帖有推广文案（【本站免费分享…】【温馨提示…】）；媒体 CDN `img.ziyuanquancdn.com` 支持 CORS。

# 真实书源模板与结构示例

> 模板只给"格式与模式"。所有选择器必须换成目标站真实结构。更多模板：`references/real-templates.txt`；案例库检索：`python scripts/kb_query.py "关键词"`。

## 模板1：笔趣阁类（Default 语法，标准小说站）

```json
[
  {
    "bookSourceName": "笔趣阁",
    "bookSourceUrl": "https://www.biquge.com",
    "bookSourceType": 0,
    "searchUrl": "/search.php?q={{key}}",
    "ruleSearch": {
      "bookList": "class.result-list@class.result-item",
      "name": "class.result-game-item-title-link@text",
      "author": "@css:.result-game-item-info-tag:nth-of-type(1)@text##作\\s*者：",
      "bookUrl": "class.result-game-item-title-link@href",
      "coverUrl": "class.result-game-item-pic@tag.img@src",
      "intro": "class.result-game-item-desc@text"
    },
    "ruleBookInfo": {
      "name": "id.info@tag.h1@text",
      "author": "#info p.0@text##作.*?：",
      "coverUrl": "id.fmimg@tag.img@src",
      "intro": "id.intro@text",
      "lastChapter": "#info p.3 a@text"
    },
    "ruleToc": {
      "chapterList": "id.list@tag.dd@tag.a",
      "chapterName": "text",
      "chapterUrl": "href"
    },
    "ruleContent": {
      "content": "id.content@html##<script[\\s\\S]*?</script>|请收藏.*"
    }
  }
]
```

## 模板2：69书吧类（POST + GBK）

```json
[
  {
    "bookSourceName": "69书吧",
    "bookSourceUrl": "https://www.69shuba.com",
    "bookSourceType": 0,
    "searchUrl": "/modules/article/search.php,{\"method\":\"POST\",\"body\":\"searchkey={{key}}&searchtype=all\",\"charset\":\"gbk\"}",
    "ruleSearch": {
      "bookList": "class.newbox@tag.li",
      "name": "tag.a.0@text",
      "author": "tag.span.-1@text##.*：",
      "bookUrl": "tag.a.0@href",
      "coverUrl": "tag.img@src"
    },
    "ruleBookInfo": {
      "name": "class.booknav2@tag.h1@text",
      "author": "class.booknav2@tag.a.0@text",
      "coverUrl": "class.bookimg2@tag.img@src",
      "intro": "class.navtxt@tag.p.-1@text",
      "kind": "class.booknav2@tag.a.1@text",
      "lastChapter": "class.qustime@tag.a@text"
    },
    "ruleToc": {
      "chapterList": "id.catalog@tag.li",
      "chapterName": "tag.a@text",
      "chapterUrl": "tag.a@href"
    },
    "ruleContent": {
      "content": "class.txtnav@html##<p>.*?</p>|<script[\\s\\S]*?</script>"
    }
  }
]
```

## 模板3：带 nextContentUrl 的正文规则

```json
[
  {
    "bookSourceName": "示例",
    "bookSourceUrl": "https://example.com",
    "ruleContent": {
      "content": "#chaptercontent@html##广告[\\s\\S]*?##",
      "nextContentUrl": "text.下一章@href"
    }
  }
]
```

错误示范（勿模仿）：

```json
{ "nextContentUrl": "a:contains(下一章)@href", "prevContentUrl": "text.上一章@href" }
```

## 模板3.5：发现页 exploreUrl（整齐两列布局）

> ⚠️ **仅当用户确认需要发现规则时才用本模板**；用户未说明时先提问（见 SKILL.md「开工前需求门禁」），不要不问就跳过。
> 发现页布局的完整规范（FlexChildStyle 真实字段、黄金值、反面清单）见 **`references/explore-layout.md`**。
> 核心：每个条目必须带 `style.layout_flexBasisPercent`（两列 `0.45`），分组标题 `1.0` + `url:""`，
> 不要写 `textAlign`/`fontWeight`（Legado 不支持）。

```json
{
  "exploreUrl": "@js:\nvar cats=[['玄幻','1'],['都市','2'],['仙侠','3'],['历史','4']];\nvar fil=[];\nfil.push({title:'分类',url:'',style:{layout_flexBasisPercent:1.0,layout_justifySelf:'center'}});\nfor(var i=0;i<cats.length;i++){fil.push({title:cats[i][0],url:'/sort/'+cats[i][1]+'/{{page}}.html',style:{layout_flexBasisPercent:0.45}});}\nJSON.stringify(fil);",
  "ruleExplore": {
    "bookList": ".list .item",
    "name": ".title@text",
    "bookUrl": "a@href",
    "author": ".author@text"
  }
}
```

## 模板4：XPath 写法

```json
[
  {
    "bookSourceName": "新笔趣阁",
    "bookSourceUrl": "https://www.xbiquge.la",
    "bookSourceType": 0,
    "searchUrl": "/search.php?keyword={{key}}",
    "ruleSearch": {
      "bookList": "//div[@class=\"result-item\"]",
      "name": "//h3/a/text()",
      "author": "//p[@class=\"result-game-item-info-tag\"][1]/span[2]/text()",
      "bookUrl": "//h3/a/@href"
    },
    "ruleToc": {
      "chapterList": "//div[@id=\"list\"]/dl/dd/a",
      "chapterName": "/text()",
      "chapterUrl": "/@href"
    },
    "ruleContent": { "content": "//div[@id=\"content\"]" }
  }
]
```

## 模板5：API/JSONPath 型（含有声书 webView）

```json
[
  {
    "bookSourceName": "猫耳FM",
    "bookSourceUrl": "https://www.missevan.com",
    "bookSourceType": 1,
    "searchUrl": "https://www.missevan.com/dramaapi/search?s={{key}}&page=1",
    "ruleSearch": {
      "bookList": "$.info.Datas",
      "name": "$.name",
      "author": "$.author",
      "bookUrl": "https://www.missevan.com/mdrama/drama/{{$.id}},{\"webView\":true}"
    },
    "ruleContent": {
      "content": "https://static.missevan.com/{{//*[contains(@class,\"pld-sound-active\")]/@data-soundurl64}}",
      "sourceRegex": ".*\\.(mp3|m4a).*"
    }
  }
]
```

## 模板6：订阅源（RssSource，文章流站）

> 完整规范（字段全表/解析路径/坑表）见 `references/rss-source-spec.md`。字段名全是 `sourceXxx`/`ruleXxx`。

```json
{
  "sourceName": "示例订阅源",
  "sourceUrl": "https://www.example.com/page/{{page}}",
  "sourceIcon": "https://www.example.com/favicon.png",
  "sourceGroup": "资源",
  "sourceComment": "文章流订阅源：分类导航 + 搜索，正文自动净化",
  "enabled": true,
  "enableJs": true,
  "enabledCookieJar": true,
  "loadWithBaseUrl": true,
  "preload": true,
  "singleUrl": false,
  "type": 0,
  "articleStyle": 2,
  "header": "{\"User-Agent\":\"Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36\"}",
  "sortUrl": "🆕 最新::https://www.example.com/page/{{page}}\n分类A::https://www.example.com/catA/page/{{page}}",
  "ruleArticles": "article.post-card:not(.post-sticky)",
  "ruleTitle": ".post-title a@text",
  "rulePubDate": ".post-meta .meta-item.0@text",
  "ruleImage": "<js>var v=String(java.getString('video@poster')||'');if(v){result=v;}else{var l=java.getStringList('.post-gallery img@src');result=(l&&l.size()>0)?String(l.get(0)):'';}</js>",
  "ruleLink": ".post-title a@href",
  "ruleNextPage": "page",
  "ruleContent": "<js>var h=String(java.getString('.post-body@html')||'');h=h.replace(/【本站免费分享[^】]*】/g,'');result='<!DOCTYPE html><html><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\"><style>body{margin:0;padding:12px;font-size:16px;line-height:1.8}img{max-width:100%;display:block;margin:8px auto;border-radius:6px}video{width:100%;max-height:80vh;display:block;margin:8px auto;background:#000;border-radius:8px}</style></head><body>'+h+'</body></html>';</js>",
  "style": "body{font-size:16px;line-height:1.8;padding:12px;} img{max-width:100%;} p{margin:8px 0;}",
  "customOrder": 0,
  "lastUpdateTime": 0,
  "searchUrl": "https://www.example.com/page/{{page}}?s={{key}}"
}
```

**要点**：
- **不填 `ruleDescription`**（填了打开文章只显示摘要，不加载正文）。
- `ruleImage` 必须单值；视频帖优先 `video@poster`。
- `ruleContent` 构建完整 HTML；视频保留 `<video controls>` 内嵌播放。
- 导入格式：编辑界面 `{}` 单对象；文件导入 `[{...}]` 数组。

## 常见 HTML 结构 → 规则对照

### 标准列表（有封面）

```html
<div class="book-list"><div class="item">
  <img src="cover.jpg" class="cover"/>
  <a href="/book/1" class="title">书名</a>
  <p class="author">作者：张三</p>
</div></div>
```

```json
{ "bookList": ".book-list .item", "name": ".title@text", "author": ".author@text##^作者：", "bookUrl": "a@href", "coverUrl": "img@src" }
```

### 无封面 + 信息合并 + 多同名标签

```html
<div class="hot_sale"><a href="/biquge_317279/">
  <p class="title">末日成神</p>
  <p class="author">科幻灵异 | 作者：钱真人</p>
  <p class="author">连载 | 更新：第69章 魔师</p>
</a></div>
```

```json
{
  "bookList": ".hot_sale",
  "name": ".title@text",
  "author": ".author p.0@text##.*\\| 作者：##",
  "kind": ".author p.0@text##\\|.*##",
  "lastChapter": ".author p.1@text##.*更新：##",
  "bookUrl": "a@href",
  "coverUrl": ""
}
```

（索引 `.0`/`.1` 区分两个 `<p class="author">`；也可用捕获组 `##.*作者：(.*)##$1`。）

### 懒加载图片（用 `||` 兜底）

```html
<img class="lazy" data-original="cover.jpg" src="placeholder.jpg"/>
```

```json
{ "coverUrl": "img.lazy@data-original||img@src" }
```

`||` 表示前一条规则取不到值时用下一条兜底，适用于所有字段。

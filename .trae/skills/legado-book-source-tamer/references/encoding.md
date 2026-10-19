# 网站编码检测与配置

> 乱码是 GBK 站书源失败的头号原因。编码在**抓 HTML 之前**检测，一次检测全程使用。

## 检测流程

```bash
python scripts/smart_fetch.py --detect <url>
```

检测优先级：用户指定 charset → HTTP Content-Type header → HTML `<meta charset>` → chardet 统计 → 默认 utf-8。

## 结果处理

| 检测结果 | 动作 |
|----------|------|
| utf-8 | 什么都不用配（默认） |
| gbk / gb2312 / gb18030 | 所有请求与书源配置统一用 `"charset": "gbk"` |

## 书源中的编码配置

搜索 URL（POST 例）：

```json
"searchUrl": "/modules/article/search.php,{\"method\":\"POST\",\"body\":\"searchkey={{key}}&searchtype=all\",\"charset\":\"gbk\"}"
```

搜索 URL（GET + GBK 关键词编码例）：

```json
"searchUrl": "/search.php?keyword={{java.encodeURI(key,'GBK')}}&page={{page}}"
```

JS 版：

```js
@js:
var option = {"charset": "gbk", "method": "POST", "body": String(body)};
"https://www.example.com/search," + JSON.stringify(option)
```

## 常见编码对照

| 页面声明 | 书源 charset 值 |
|----------|----------------|
| UTF-8 | 省略 |
| GBK | "gbk" |
| GB2312 | "gbk" |
| GB18030 | "gbk" |

## 禁止

- 不检测就抓 HTML。
- 重复检测（一次全程够用）。
- 检测出 GBK 却不在 searchUrl / 请求里声明。
- 用 gb2312/gb18030 当值——统一写 `gbk`。

更深资料：`references/encoding-guide.md`（原版完整指南）。

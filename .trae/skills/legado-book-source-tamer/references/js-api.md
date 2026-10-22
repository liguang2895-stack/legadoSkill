# Legado JS 开发指南（Rhino 1.8.0 环境）

书源规则里 `@js:` 前缀、`{{...}}` 内嵌 JS、以及各规则字段的 `@js:` 尾段都在 Rhino 引擎执行。

## 环境约束

| 配置项 | 说明 |
|--------|------|
| 引擎 | Rhino 1.8.0 |
| 变量声明 | 用 `var`，避免 `const`/`let`（作用域问题） |
| Java 互操作 | `java.*` 对象；`Packages.java.*` 访问任意 Java 包 |

## 核心变量表

| 变量 | 类型 | 说明 |
|------|------|------|
| `java` | 当前类 | 万能工具箱（下方全部方法） |
| `baseUrl` | String | 当前页面 URL |
| `result` | Any | 上一步结果 |
| `book` | Book | 书籍信息（`book.name/author/coverUrl/intro/bookUrl/tocUrl/durChapterTitle/durChapterIndex/durChapterPos`） |
| `chapter` | Chapter | `chapter.title/url/index/baseUrl` |
| `source` | BaseSource | 书源操作（见下） |
| `cookie` | CookieStore | Cookie 管理 |
| `cache` | CacheManager | 缓存 |
| `key` / `page` | String/Int | 搜索词 / 页码（searchUrl 场景） |

## 网络请求

```js
java.ajax(url)                      // 返回字符串
java.connect(url)                   // 返回 StrResponse（.code()/.body()/.url()）
java.get(url, headers, timeout)
java.post(url, body, headers, timeout)
java.head(url, headers, timeout)
java.ajaxAll(urlList)               // 并发批量

// WebView 三兄弟（处理动态渲染页）
java.webView(html, url, js)         // 执行 JS 后返回渲染 HTML
java.webViewGetOverrideUrl(html, url, js, regex)  // 捕获跳转 URL
java.webViewGetSource(html, url, js, regex)       // 捕获资源 URL
```

### ⚠️ java.ajax 与 java.get/post 的本质区别（源码级，反爬站必读）

| | `java.ajax(url)` | `java.get/post` |
|---|---|---|
| 实现 | `AnalyzeUrl(source=getSource())` → OkHttp | Jsoup 直连 |
| 书源 header（UA/自定义头） | ✅ **自动注入** | ❌ 只用手动传入的 headers |
| CookieJar（enabledCookieJar） | ✅ 自动携带与保存 | ❌ 不带 |
| 重定向跟随 | ✅ 自动 | ❌ 不跟随 |
| URL+options 格式 | ✅ 支持 `url,{"method":"POST",...}` | ❌ 不支持 |

**结论**：反爬站（GoEdge/UA 校验/需要 Cookie 预热/302 跳转）**一律用 `java.ajax`**。
`java.get/post` 只适合简单的无鉴权接口。
典型症状：`java.post` 被 WAF 挑战（无 UA 裸奔），换 `java.ajax` 即通。

### POST body 编码规则（Legado 源码行为，极易踩坑）

`AnalyzeUrl` 对 POST body 的分支处理：

| body 类型 | 行为 | 服务端收到 |
|-----------|------|-----------|
| JSON/XML 开头 | 原文发送（`postJson`） | application/json |
| form 且**无 Content-Type 头** | 自动 form 编码（`analyzeFields`：按 `k=v` 拆分，value 自动 URLEncoder） | `data=abc%2Bdef%3D` ✓ |
| form 且**有 Content-Type 头** | 走 `postJson` 分支！ | application/json ❌ |

**所以：form 类 POST 的 body 不要写 Content-Type 头**（写了反而变成 JSON 发送，PHP `$_POST` 收不到）。
```js
// ✅ 正确：body 传原始值，不写 Content-Type → Legado 自动编码
var opt = JSON.stringify({method:'POST', body:'data='+enc});
// ❌ 错误：写了 Content-Type → 被当 JSON 发，$_POST 为空
var opt = JSON.stringify({method:'POST', body:'data='+enc, headers:{'Content-Type':'application/x-www-form-urlencoded'}});
```
另注意：`url,{...}` 的 options JSON **不要嵌套**（headers 里再套对象）——validator 解析正则 `,\{[^}]*\}$` 不支持嵌套，真机 GSON 可以但校验器会解析失败；能不带 headers 就不带。

## 编码解码

```js
java.base64Encode(str) / java.base64Decode(str, charset)
java.hexEncodeToString(str) / java.hexDecodeToString(hex)
java.encodeURI(str) / java.encodeURI(str, "UTF8")
java.strToBytes(str, "UTF8") / java.bytesToStr(bytes, "GBK")
```

## 加密解密

```js
var cipher = java.createSymmetricCrypto("AES/CBC/PKCS5Padding", key, iv)
cipher.encryptHex(data); cipher.encryptBase64(data); cipher.decryptStr(data)

var rsa = java.createAsymmetricCrypto("RSA"); rsa.setPublicKey(pub); rsa.encryptBase64(data, true)

java.md5Encode(str) / java.md5Encode16(str)
java.digestHex(data, "SHA256") / java.digestBase64Str(data, "SHA1")
java.HMacHex(data, "HmacSHA256", key)
```

## 内容解析 / 书源 / 缓存 / Cookie

```js
java.getString(ruleStr, content, isUrl)   // 用规则字符串从内容取值
java.getElements(ruleStr)
java.setContent(content, baseUrl)

source.getKey(); source.getVariable(); source.setVariable(v)
source.put(key, value); source.get(key)            // 自定义 KV（存 token、备用域名）
source.getLoginHeader(); source.putLoginHeader(h)

cache.put(key, value, saveTime); cache.get(key)    // saveTime 秒
cache.putFile(key, v, t); cache.getFile(key)
cache.putMemory(key, v); cache.getFromMemory(key)

cookie.getCookie(url); cookie.setCookie(url, str); cookie.removeCookie(url)

java.downloadFile(url); java.readTxtFile(path, "UTF8")
java.unzipFile(zipPath); java.unrarFile(p); java.un7zFile(p); java.unArchiveFile(p)
java.getTxtInFolder(folderPath)

java.log("调试"); java.toast("提示"); java.longToast("长提示")
```

扩展 API（aes/jsoup 封装等）详见 `references/js-extend-methods.md`。

## Rhino 跨语言坑（Java 互操作）

### 1. ConsString 陷阱（ClassCastException 高发区）

JS 字符串拼接（`a + b`）产生的是 Rhino 的**惰性 ConsString**，不是 `java.lang.String`。
把它传给任何 Java 方法（`java.ajax`、`java.post`、`java.base64Decode`、`JSON.parse` 参数……）都会报：
```
org.mozilla.javascript.ConsString cannot be cast to java.lang.String
```

**修复：所有跨语言传递的字符串都用数组 join 拍平**（join 结果是真 String）：
```js
function S(){
    var a=[];
    for(var i=0;i<arguments.length;i++){
        if(arguments[i]!=null)a.push(String(arguments[i]));
    }
    return a.join('');
}
// 用法：java.ajax(S(host, '/search?q=', key))  而不是  java.ajax(host + '/search?q=' + key)
```
涉及位置：URL 拼接、body 拼接、header 值、`@js:` 规则返回值（return 给规则引擎也算跨语言）。

### 2. Java 字符串 vs JS 字面量比较

`String(result)` 拿到的是 Java String 包装，与 JS 字面量 `===` 比较**永远 false**：
```js
if (result === 'ok')          // ❌ 可能永远 false
if (String(result) === 'ok')  // ✅ 先 String() 拍平
if (String(result).indexOf('ok') >= 0)  // ✅ 更稳
```

### 3. 正则字面量跨行

JS 正则里的 `\d` 等转义在 JSON 字符串中要写 `\\d`；规则串里用 `[0-9]` 替代 `\d` 可同时兼容 validator 的已知转义 bug。

## Mock DOM：在无浏览器环境执行页面签名 JS（反爬签名站★）

很多反爬站（rrssk 系合作站、GoEdge WAF 站）的签名算法放在页面引用的 `signJs` 里，运行时依赖一组环境指纹（`document`、`window`、`navigator`、`Object.prototype.toString` 等）。**不要逐项正则提取常数**（只抗常数轮换不抗算法变化），而是**用 Mock DOM 完整执行它**：

```js
// 1. 抓页面拿 _t token 和 signJs 地址（java.ajax，走书源 UA）
// 2. 造假 DOM（下为 rrssk v17 实测完整版，14 项指纹 = 31 分）
var _toString = Object.prototype.toString;
function makeEl(tag){
    tag = String(tag||'div');
    return {nodeType:1, nodeName:tag.toUpperCase(), tagName:tag.toUpperCase(),
        style:{}, ownerDocument:null, setAttribute:function(){},
        getAttribute:function(){return null;}, cloneNode:function(){return makeEl(tag);},
        appendChild:function(c){return c;}, addEventListener:function(){},
        removeEventListener:function(){}};
}
var fakeDoc = {nodeType:9, nodeName:'#document',
    createElement:function(tag){var el=makeEl(tag);el.ownerDocument=fakeDoc;return el;},
    createElementNS:function(ns,tag){var el=makeEl(tag);el.ownerDocument=fakeDoc;return el;},  // v17+
    getElementsByTagName:function(n){return n==='html'?[fakeDoc.documentElement]:[];},
    addEventListener:function(){}, removeEventListener:function(){}};
fakeDoc.documentElement = {nodeType:1, nodeName:'HTML', tagName:'HTML', parentNode:null, style:{},
    contains:function(){return false;}};                                                     // v17+
fakeDoc.documentElement.parentNode = fakeDoc;
fakeDoc.body = {nodeName:'BODY', nodeType:1};
fakeDoc.implementation = {};
var fakeWin = {location:{href:host+'/00PB.html'},
    addEventListener:function(type,h){try{if(h)h({isTrusted:true,type:type});}catch(e){}}};
var fakeNav = {userAgent:'Mozilla/5.0 (Linux; Android 13; K) ...'};                          // v17+
// Object.prototype.toString 补丁（指纹项）
Object.prototype.toString = function(){
    if(this===fakeDoc)return '[object HTMLDocument]';
    if(this&&this.nodeType===1&&this.nodeName==='DIV')return '[object HTMLDivElement]';
    return _toString.call(this);
};
// 3. eval 执行 signJs，取它挂到 window 的签名函数（navigator 作为参数传入）
var __SIGN = null;
try {
    var mkSign = eval('(function(document,window,navigator){'+signJs+'\nreturn window.__SIGN;})');
    __SIGN = mkSign(fakeDoc, fakeWin, fakeNav);
} finally {
    Object.prototype.toString = _toString;   // ★ 必须还原，否则污染后续规则
}
// 4. 调用签名函数（参数按站点算法要求，常见：编码后的关键词、token、时间戳）
var sg = String(__SIGN.f(__enc(key), t, ts));
```
- **必须 finally 还原 `Object.prototype.toString`**——不还原会污染同一次会话里其它 JS 规则。
- 执行后检查返回值非空/非 `'00000000'`，否则抛错（说明指纹未过）。
- 该方案实测可复现浏览器签名值（逐位一致）。

### 指纹军备竞赛：签名站升级的识别与修复（★ 长期维护必读）

签名站会**不定期增补指纹项**（实测：rrssk v16→v17 一次加了 3 项，总分改为"必须恰好 31 分"）。
**症状**（二选一）：
- 抛 `ReferenceError: "xxx" 未定义`（新指纹引用了 Mock DOM 没有的对象，如 `navigator`）；
- 签名返回 `00000000`（总分不满/超，或某项类型不对）。

**修复流程（最小改动原则）**：
1. 抓最新 signJs（注意 URL 带版本号如 `?action=signJs&v=17-20261014`），**通读它检查了哪些项**；
2. 逐项在 Mock DOM 里补齐（如 `createElementNS`、`documentElement.contains`、`fakeNav.userAgent`）；
3. 检查计分制：可能是"≥N 分"或"**恰好 N 分**"——恰好制下多一项少一项都失败；
4. 注意新事件检查（如 `isTrusted` 事件）：fakeWin.addEventListener 同步回调 `{isTrusted:true}` 可满足；
5. 用真 Rhino 端到端复测：签名非零 + 搜索出结果；
6. **只改搜索 Mock DOM，不要动目录/正文逻辑**（与签名无关，避免引入新问题）。

**会话绑定**：搜索类接口常把 `_t` 与 PHPSESSID 绑定——GET 拿 `_t` 和 POST 必须**同一会话**（书源 `enabledCookieJar: true` + java.ajax 自动管理 CookieJar）。

### 终局方案：注入式守卫绕过（★ 军备竞赛反复失效时应立刻转用）

补指纹只是**过渡**：轮换型签名站会每日加指纹项（实测 rrssk 5 天内 31→44 分），Mock DOM 永远慢一拍。
长期方案是**读守卫的规则，不模拟环境**：

1. **提取守卫变量与要求值**（三种常见形态全覆盖）：
   ```js
   var inj='';
   var g1=src.match(/typeof\s+([A-Za-z_$][\w$]*)\s*!==?\s*["']number["']\s*\|\|\s*\1\s*!==?\s*(\d+)/);
   if(g1){inj+=g1[1]+'='+g1[2]+';';}
   var gr=/if\s*\(\s*([A-Za-z_$][\w$]*)\s*!==\s*(\d+)\s*\)\s*\{?\s*return\s*["']00000000["']/g;
   var gm;while((gm=gr.exec(src))!=null){if(inj.indexOf(gm[1]+'=')<0){inj+=gm[1]+'='+gm[2]+';';}}
   var g4=src.match(/([A-Za-z_$][\w$]*)\s*!==\s*(\d+)\s*\?\s*["']00000000["']/);
   if(g4&&inj.indexOf(g4[1]+'=')<0){inj+=g4[1]+'='+g4[2]+';';}
   ```
2. **注入位置**：`window["__"+"SIGN"]=` 赋值之前（兜底锚点：`function \w+\(s,t,ts\)`、探针 IIFE `(function(){var X=[`）。
   必须在所有 `_score+=` 测量代码**之后**，否则会被覆盖。
3. **为什么"赋值注入"而不是"条件空改"**：指纹分常**参与签名哈希**（实测 `a8 ^= (_score*7+3)`）——
   只跳过检查，哈希仍按错误分数算出，服务端照样拒；注入正确值才让守卫与哈希同时正确。
4. **第二道防线**：`signJs.replace(/if\s*\(\s*[^()]*!==\s*\d+[^()]*\)/g,'if(false)')` 再试
   （保持 `if(...)→if(false)` 等括号结构，花括号安全；只针对含 `!==数字` 的 if 头）。
5. **诱饵警报**：签名 JS 可能内置 `var _decoy=function(){return "00000000"}` / `__SIGN_DECOY` 死代码，
   "全局替换 00000000" 式绕过会上钩；变量注入式不受影响。
6. **Mock DOM 降级**：用注入式后，mock 只需**执行不抛异常**，不再需要精确得分——对任何指纹增删免疫。
7. **诊断**：`java.log('INJECT:'+inj)`（应非空）与 `SIG_OK`——真机失效时从日志直接判断正则漏了哪种守卫形态。
   落地模板见案例《猫扑小说》v18 searchUrl（`__collect/__anchor/__injectAt/__exec` 四函数 + 第二道防线）。

## 302 跳转：让主请求跟随，别在响应体里捞 URL（★ 搜索偶发为空的经典坑）

**症状**：某些关键词能搜、某些返回空列表；日志显示 POST 成功但最终 URL 回退到首页。

**根因**：搜索 POST 常 302 到 `?action=find&...&q=<token>&page=1`。该 URL **只存在于 Location 头**，
响应体里没有。若源内用 `java.ajax` 自己 POST 再正则从响应 HTML 捞 URL：
- 结果多（出现翻页链接）→ 翻页链接把 URL 泄进 body → 侥幸成功；
- 结果少（单页无翻页）→ 捞不到 → 回退首页 → 空列表。
看起来"某些关键词坏了"，实际是"**结果数**决定了成败"。

**正确做法**：searchUrl 只负责算签名并**返回 `URL + ',' + options`**，把 POST 交给 Legado 主请求：

```js
var body = 'keyword=' + enc + '&_t=' + encodeURIComponent(t) + '&_ts=' + ts + '&_s=' + encodeURIComponent(sig);
var bjs = "var s=''+result;var pn=page;if(pn>1){/* 从结果页提 action=find&v= 片段拼 &page=N 再 java.ajax */}else{s;}";
var opt = ',' + JSON.stringify({method:'POST', body:body, headers:{Referer:BASE+'/00PB.html'}, bodyJs:bjs});
BASE + '/?action=search' + opt;
```

- 主请求自动跟随 302；`bodyJs` 在**最终响应体**上求值（源码 AnalyzeUrl.kt:507），`result`=响应体、`page`=页码。
- 注意 options 前必须带**逗号**（`URL,{...}` 格式）。
- 只有 POST body 是 form 且**不要设 Content-Type**，Legado 才会按表单编码（见上文 POST 编码规则）。

**验证要忠实引擎**：用 Jsoup 解析 + 真实执行规则体，不要正则扫原始 HTML——
`onclick="...&amp;t=..."` 经 Jsoup 属性取值已反转义，正则直扫会误判"取不到 t="。

## 动态密钥/IV 轮换（★ 每日换密钥的 API 站必读）

**特征**：详情页引用一个**随机名 JS 文件**（如 `/templates/js/7M1GcU9Yk1yJcTNE3AEOsIIGEj5DnmN.js`），
里面是 `new AESCrypt('密钥')` + `Utf8.parse('IV')`；密钥每天/每次发布轮换。

**症状**：API 昨天正常今天 `code:-1`；硬编码密钥的书源突然全部失败。

**修复：动态提取，永不硬编码**：
```js
var sre = /src="([^"]*\/templates\/js\/[A-Za-z0-9]{20,}\.js[^"]*)"/g;
var sm, cands = [];
while ((sm = sre.exec(html)) !== null) {
    var p = String(sm[1]);
    if (p.indexOf('http') !== 0) { p = 'https://www.mopbook.com' + p; }
    cands.push(p);
}
for (var ci = 0; ci < cands.length; ci++) {
    var jsText = '';
    try { jsText = String(java.ajax(cands[ci])); } catch(e) { continue; }
    var km = jsText.match(/new AESCrypt\('([^']+)'\)/);
    var vm = jsText.match(/Utf8\.parse\('([^']+)'\)/);
    if (km && vm) { ckey = String(km[1]); iv = String(vm[1]); break; }
}
```
- 抓不到密钥时走**兜底目录**（详情页内嵌章节列表），不能空手而归。
- 排查方法：解密浏览器真实请求的密文（HAR）验证算法是否正确——用已知密钥本地加密结果与密文**逐字节比对**，一致即算法无误，问题只在密钥本身。

## API 分页重叠与去重（长书目录必读）

部分站的章节 API 分页**区间重叠**（实测：689 章书 page1=1..207、page2=99..198）。
**不要假设 page1=1..100、page2=101..200**。合并多页时必须按主键去重：

```js
var seen = {};
...
var u = String(j.data[i].chapterurl);
if (seen[u]) continue;
seen[u] = 1;
arr.push({o: parseInt(j.data[i].chapterorder), t: String(j.data[i].chaptername), u: u});
...
arr.sort(function(a, b) { return a.o - b.o; });   // 最后按章号排序
```

**兜底目录排序**：详情页内嵌目录（"最新章节"块在前 + "1-100章"块在后）顺序是乱的，
必须从 URL 提取章号排序（`-([0-9]+).html` 最可靠），并同样去重：
```js
var nm = u2.match(/-([0-9]+)(?:-[0-9]+)?\.html/);
var o2 = nm ? parseInt(nm[1]) : 999999;
```

## java.webView 的 js 参数限制（易错！）

**js 参数在浏览器环境执行（可用 DOM/BOM）；返回后的处理回到 Rhino（只能 ES5）。**

```js
// ✅ js 参数里用 DOM（浏览器环境）
var html = java.webView(html, url,
  'setTimeout(function(){' +
  '  var html = document.documentElement.outerHTML;' +
  '  window.legado.getHTML(html);' +
  '}, 5000);');

// ✅ 返回后在 Rhino 里处理：只能 ES5，var + 传统函数
var content = html.replace(/<script[\s\S]*?<\/script>/g, '');
```

| 特性 | 支持 |
|------|------|
| ES5（var、function） | ✅ |
| 箭头函数 / 部分 ES6 | ⚠️ 谨慎 |
| DOM/BOM（document、window） | ❌（仅限 js 参数内的浏览器执行段） |

## JSONPath 规则（API 型站点）

- 前缀 `$.`：`$.data.books[*]`；列表规则返回数组。
- 与 CSS 混用：`$.data.list[*]` 后每条记录里 `$.title`、`$.url` 取字段。
- 完整官方实现见调试器内 `scripts/debugger/engine/kotlin_reference/AnalyzeByJSonPath.kt`。

# 加密 API 站与反爬验证（ALTCHA PoW / 信封加密 / 会话共享）

适用：接口返回 JSON 但**请求被加密签名**、**响应是密文**、或**不弹验证码但接口 403** 的站（SPA + XHR 架构常见）。
完整实战案例：`legadoSkill/assets/zjread.json参考.txt` + `zjread技术笔记.md`（纸间 zjread.cc，2026-10 实测可用）。

**总原则：复刻客户端协议，而不是用 WebView 硬渲染。** 协议一旦跑通，四链路全走 `java.get/java.post`，快、稳、可缓存。

---

## 一、决策树：正文 403/空内容先分清是哪种墙

| 症状 | 判断 | 对策 |
|------|------|------|
| 页面含 "Just a moment" / CF 盾 | Cloudflare 挑战 | 见 `webview-login-notes.md`；若能绕开接口则优先绕 |
| 接口 403/4001，**页面无验证码组件** | 无感 PoW（ALTCHA 等） | **本文 §二 本地 PoW**（免人工）★ |
| 响应体是 `{data, nonce}` 密文 | 信封加密 | **本文 §三 复刻协议** |
| 响应含 `key_mode` / `key_material` | 章节独立密钥 | **本文 §四 本地重派生**（绕开 WASM） |
| 规则字段是 POST，参数没处放 | Legado 传参限制 | **本文 §五 bootstrap 携参** |

---

## 二、ALTCHA 本地 PoW 换 token（免人工验证）★

**发现**：页面无验证码但接口 403。在页面 JS bundle 里搜 `captcha`/`altcha`/`challenge`，常能找到隐藏接口：

- `GET  /api/captcha/altcha/challenge` → 挑战参数
- `POST /api/captcha/altcha/verify` → 返回 `captcha_token`（通常 300s 有效）

**求解**（SHA-256 工作量证明，成本极低）：

```js
// parameters: {algorithm:"SHA-256", cost, keyLength, keyPrefix, salt, nonce}
// for counter in 0..200000:
//   digest = SHA256(salt + nonce + counter(4字节大端))
//   再迭代 SHA256 cost-1 次
//   hex(digest) 以 keyPrefix 开头 → 解 = {counter, derivedKey}
function sha256(bytes) {
  var md = Packages.java.security.MessageDigest.getInstance("SHA-256");
  return md.digest(bytes);
}
function solveAltcha(p) {
  var prefix = String(p.keyPrefix).toLowerCase(), cost = p.cost || 1;
  var base = String(p.salt) + String(p.nonce);
  for (var c = 0; c <= 200000; c++) {
    var d = sha256(strToBytes(base + hex32BE(c)));   // 大端 4 字节 counter
    for (var i = 1; i < cost; i++) d = sha256(d);
    if (hex(d).substring(0, prefix.length) === prefix) return {counter: c, derivedKey: hex(d)};
  }
  throw "ALTCHA 求解失败";
}
```

**缓存**（关键，避免每章重解）：

```js
// 挑战解一次，token 存源变量，300s 内复用
source.put("zj_captcha_v1", JSON.stringify({token: t, exp: nowSec + 300}));
```

**为什么必须走这条路**：WebView 过 CF 盾 5-30s/次且可能要手动点；本地 PoW 0.01s、零人工、纯算法无浏览器指纹，盾升级也不影响。**遇到 403 先搜 JS 找 PoW 接口，再考虑 WebView。**

---

## 三、信封加密协议复刻（bootstrap → HKDF → AES-GCM + HMAC）

### 3.1 抓协议（Python 先跑通，再移植 jsLib）

1. 首页 → 主 JS bundle → 搜 `bootstrap`/`encrypt`/`hkdf`/`X-Signature`。
2. `GET /api/bootstrap` → 拿 `session_id` + `key_material`。
3. 搜 JS 里的 info 字符串（如 `"novel-api-aes-v1"`）确认密钥派生参数：

```js
aesKey  = HKDF-SHA256(key_material, salt = session_id, info = "<站点的aes-info>", 32)
hmacKey = HKDF-SHA256(key_material, salt = session_id, info = "<站点的hmac-info>", 32)
```

4. 找签名串拼接（通常是 `METHOD\npath\ntimestamp\nnonce\nbodyHash`），复刻五头。

### 3.2 Rhino 实现要点（踩过的坑）

| 坑 | 正确做法 |
|----|---------|
| GCM 用 IvParameterSpec → SunJCE 拒绝 | `new Packages.javax.crypto.spec.GCMParameterSpec(128, iv)` |
| `java.base64Encode` 按 UTF-8 损坏二进制 | **手写 base64**（表 `A-Za-z0-9+/`，逐 3 字节） |
| `byte & 255` 回写报 `Cannot convert 151 to Byte` | `w > 127 ? w - 256 : w` 收窄 |
| 反射 `Packages.java.lang.reflect.Array` 被真机阻止 | 只用 `java.strToBytes/bytesToStr/hexDecodeToByteArray` 等原生方法 |
| 随机数 | `KeyGenerator.getInstance("AES")` 生成后取 encoded 字节 |

```js
// 加密：nonce=随机12字节，data=AES-GCM(aesKey, nonce, JSON.stringify(payload))
// 签名：signature = HMAC-SHA256(hmacKey, "POST\n"+path+"\n"+ts+"\n"+nonce+"\n"+sha256hex(body))
// 五头：X-Session-ID / X-Timestamp / X-Nonce / X-Signature / X-Key-Version
```

### 3.3 jsLib 作用域约束

**jsLib 没有 `java`/`source` 绑定**（独立 SharedJsScope，空绑定）→ 库函数用 `zjInit(java, source)` 由每条规则入口显式注入：

```js
// jsLib
function zjInit(j, s) { J = j; S = s; }
// 规则
"@js:zjInit(java,source); zjPost('/api/search',{keyword:key})"
```

---

## 四、章节正文本地解密（绕开 WASM）★

响应 `key_mode=chapter` 时，正文密钥不是会话密钥，而是按章派生：

```js
chapterKey = HKDF-SHA256(key_material,
                         salt = book_id + "\n" + chapter_id + "\n" + version + nonce,
                         info = "novel-chapter-aes-v1", 32)
plain = AES-256-GCM-Decrypt(chapterKey, nonce, data)
```

- **不要逆向站点 WASM 解密模块**——HKDF 是标准算法，`key_material` 在 bootstrap 已拿到，纯 JS/Java 重派生即可（本站实测 77 段落全解出）。
- salt 的 `version`/`nonce` 来自**响应体字段**；拼接时 nonce 用原始字节。
- 正文结果常见形态 `{paragraphs:[{text}|{image}]}` → 拼接 `\n\n`，图片转 `<img src>`。

---

## 五、Legado 规则传参技巧：bootstrap GET 携参 ★

**痛点**：搜索/详情/目录/正文全是 POST，Legado 规则链只传 URL 字符串，业务参数（book_id/chapter_id）没处放。

**解法**：把参数藏进站点本来就存在的 GET 路径 query，各规则从 `baseUrl` 取回：

```js
function zjUrl(k, v){ return BASE + '/api/bootstrap?' + k + '=' + encodeURIComponent(v) }
function zjParam(url, k){ var m = String(url).match(new RegExp('[?&]' + k + '=([^&]+)')); return m ? decodeURIComponent(m[1]) : '' }
```

- 搜索：`searchUrl = BASE + '/api/bootstrap?zjk=' + key + '&zjp=' + page`
- 详情/目录：`bookUrl = zjUrl('zjb', bookId)`；`tocUrl` 同
- 正文：`chapterUrl = zjUrl('zjc', chapterId)`

通用：任何 POST 型 API 站都可以选一个无害的 GET 路径当参数载体，不会 404 也不惹眼。

---

## 六、字段预取缓存（ruleBookInfo.init 一次取详情）

详情页 8 个字段各自 `@js` = 8 次请求 + 8 次解密。改为 `init` 一次性取数、算好、塞缓存，其余字段只读缓存：

```js
// ruleBookInfo.init
var d = JSON.parse(zjPost('/api/book/detail', {book_id: id}));
java.put('zjd', JSON.stringify({name, author, kind, intro, coverUrl, ...}));
// 其它字段
"name": "@js:zjInit(java,source);(JSON.parse(java.get('zjd')||'{}'))['name']||''"
```

同理会话缓存 `source.put('zj_session_v1', ...)`、token 缓存 §二。

---

## 七、错误分流：retry（换会话）vs verify（清 token）

| 错误 | 判定 | 处理 |
|------|------|------|
| 会话/签名被拒 | HTTP 401 / code 401 / 请求异常 | `retry:true` → 丢会话缓存重新 bootstrap |
| 人机验证未过 | HTTP 403 / code 403/4001 | `verify:true` → 清 captcha_token 重新挑战 |
| 其它业务错误 | code≠0 | 直接抛，不重试 |

```js
for (var i = 0; i < 2; i++) {
  var s = getSession(i === 1);            // 第 2 轮强制刷新会话
  var token; try { token = getCaptcha(s); } catch(e) { clearToken(); continue; }
  var r = post(s, '/api/book/content', {chapter_id: id, captcha_token: token});
  if (r.plain !== undefined) return render(r.plain);
  if (r.verify) clearToken();
  if (!r.retry && !r.verify) throw r.err;
}
```

---

## 八、书源骨架（加密 API 型）

```json
{
  "searchUrl": "@js:BASE + '/api/bootstrap?zjk=' + encodeURIComponent(key||'') + '&zjp=' + (page||1) + ',{\"headers\":{...}}",
  "ruleSearch": {
    "bookList": "@js:zjInit(java,source);var kw=zjParam(baseUrl,'zjk');...out.push(JSON.stringify({...}))",
    "name": "$.name", "author": "$.author", "bookUrl": "$.bookUrl", "coverUrl": "$.coverUrl"
  },
  "ruleBookInfo": { "init": "@js:...java.put('zjd',...)", "name": "@js:...(java.get('zjd'))..." },
  "ruleToc": { "chapterList": "@js:...out.push(JSON.stringify({title,url:zjUrl('zjc',id)}))" },
  "ruleContent": { "content": "@js:zjInit(java,source);zjContent(zjParam(baseUrl,'zjc'))" }
}
```

硬性要点：

- `bookList` **必须返回字符串数组**：元素 `JSON.stringify(obj)`，字段用 `$.field` 读（直接返回对象数组会 `ClassCastException: String cannot be cast to List`）。
- 目录过大（>200KB 加密 JSON）别硬解密 → 目录走 WebView 提取 DOM，或找精简目录接口。
- Java 字符串与 JS 字面量 `===` 永假 → 用 `String(h).indexOf('__X__') >= 0`。
- `java.webView` 的 js 参数**会被 Legado 自动重试**（约 30 次/28s）→ 注入函数写成「同步单次检查，未就绪返回 null」，别自己 setTimeout 轮询（会打架）。
- CF 验证是**按会话**的：WebView 过盾后要共享会话复用，不要每章重开；WebView 注入时带真实 Android Chrome UA（默认桌面 UA 会与 CF 的 Android 检测冲突）。

---

## 九、复刻清单（新加密站按序执行）

1. 存首页 HTML → 找主 JS bundle → 搜 `bootstrap`/`/api/`/`encrypt`/`captcha`。
2. `GET /api/bootstrap` → 记录 `session_id`/`key_material`。
3. 搜 JS 里 HKDF info 字符串 → 确认派生参数。
4. 搜签名拼接（`X-Signature`/HMAC 调用点）→ 复刻签名字符串。
5. 找 `key_mode` 分支 → 章节模式找 salt 拼接公式。
6. 搜验证码接口 → PoW 类本地实现求解器（§二）。
7. **Python 先验证全协议**（快）→ 再移植 jsLib（Rhino 限制多，对照 §3.2 坑表）。
8. 传参用 §五、预取用 §六、错误分流用 §七。
9. 交付前跑 `verify_source.py`；加密站常需 `--book-url` 跳过搜索验证。

# zjread（纸间 www.zjread.cc）全加密协议书源技术笔记

> 配套案例：`zjread.json参考.txt`（本源 = 网友可用成品 + 技术标注）
> 站点形态：SPA（Vue3 构建）+ 纯 XHR JSON API + 全信封加密 + Cloudflare 盾 + ALTCHA 人机验证。
> 本笔记提炼**可复用到其他加密 API 站**的通用模式，而非只记录 zjread 本身。

---

## 0. 总览：这类站的四道墙

| 墙 | zjread 的形态 | 通用破法 |
|----|--------------|---------|
| 人机验证 | Cloudflare 盾 + 隐藏的 ALTCHA PoW 挑战 | **本地算 PoW 自助换 token**，全程无 WebView、无人工 |
| 协议加密 | 请求 AES-256-GCM 信封 + HMAC 签名五头 | 在 jsLib 里用 `Packages.javax.crypto.*` 复刻签名与加解密 |
| 内容加密 | 正文按章独立密钥（key_mode=chapter） | 用协议给的 key_material 本地 HKDF 重派生章节密钥 |
| 传参受限 | 搜索/详情/目录/正文全是 POST JSON，规则传参无处安放 | **bootstrap GET 携参**技巧（把业务参数藏进 URL query） |

关键结论：**加密 API 站的正确姿势是「复刻客户端协议」而不是「用 WebView 硬渲染」**。一旦把协议跑通，四链路全部走 `java.get/java.post`，速度快、无验证码、可缓存。

---

## 1. 人机验证：ALTCHA 本地 PoW 自助换 captcha_token（免人工）★核心

### 1.1 发现过程

页面不显示任何验证码组件，但正文接口返回 `code=403/4001（人机验证未通过）`。在页面 JS 里搜 `captcha`/`altcha` 找到隐藏接口：

- `GET /api/captcha/altcha/challenge` — 返回挑战参数
- `POST /api/captcha/altcha/verify` — 提交解答，返回 `captcha_token`

### 1.2 挑战与求解（SHA-256 工作量证明）

challenge 返回：

```json
{
  "algorithm": "SHA-256",
  "challenge": {
    "parameters": { "algorithm": "SHA-256", "cost": 80, "keyLength": 32,
                    "keyPrefix": "0e0d", "salt": "xxxx", "nonce": "yyyy" }
  }
}
```

求解算法（altcha 标准）：

```
for counter in 0..200000:
    digest = SHA256(salt + nonce + counter的4字节大端)
    for i in 1..cost-1:  digest = SHA256(digest)     # 迭代 cost 次
    if hex(digest).startsWith(keyPrefix): return {counter, derivedKey}
```

- cost=80、keyPrefix 2 字符 → 平均 ~100 次外循环，**0.01 秒**出解，Rhino 里毫无压力。
- `counter` 的 4 字节大端编码：`x(e)` 函数，`for(r=24;r>=0;r-=8) hex += (e>>>r)&255`。

### 1.3 换 token 与缓存

verify 请求体 = `{challenge, solution:{counter, derivedKey, time}}`（经协议信封加密），响应里拿 `captcha_token`（**有效期 300 秒**）。

```js
// 缓存到源变量，300 秒内复用，避免每章重新解
source.put("zj_captcha_v1", JSON.stringify({token, exp, sid}));
```

### 1.4 为什么这是最优解（对比 WebView 方案）

| 方案 | 速度 | 人工 | 稳定性 |
|------|------|------|--------|
| WebView 过 CF 盾 | 5-30s/次 | 可能要手动点 | 差（盾升级即挂） |
| 手动点验证 | — | 每章一次 | 不可用 |
| **ALTCHA 本地 PoW** | **0.01s** | **零** | 极好（纯算法，无浏览器指纹） |

### 1.5 通用启示

遇到「不弹验证码但接口 403」的站：**先搜 JS 里的 captcha/verify/challenge 字样**，很多站用的是无感 PoW（ALTCHA/FriendlyCaptcha/hCaptcha 无感模式），本地算力就能过，根本不用碰 WebView。

---

## 2. 加密 API 协议：bootstrap → HKDF 双键 → AES-GCM 信封 + HMAC 签名

### 2.1 会话引导

```
GET /api/bootstrap
→ {session_id, key_material(base64), ...}
```

由 `key_material` 用 HKDF-SHA256 派生双密钥（**注意 HKDF 的 salt 是 session_id**）：

```js
aesKey  = HKDF(key_material, salt=session_id, info="novel-api-aes-v1", len=32)
hmacKey = HKDF(key_material, salt=session_id, info="novel-hmac-v1",    len=32)
```

HKDF 实现（Rhino 无 crypto 库，用 `javax.crypto.Mac` 手写）：

```js
function hkdf(ikm, salt, info, len){        // extract + expand
  var prk = HMAC(salt, ikm);
  var out = "", t = null, i = 1;
  while (out.length < 2*len) {
    t = HMAC(prk, concat(t, info, i));      // t 首次为 null
    out += hex(t); i++;
  }
  return bytes(out.substring(0, 2*len));
}
```

### 2.2 请求信封（每次 POST）

1. **加密**：`nonce = 随机12字节`，`data = AES-256-GCM(aesKey, nonce, JSON.stringify(payload))`。
2. **签名五头**（缺一不可）：

```js
timestamp = 秒级时间戳
nonce     = base64url(随机18字节)
bodyHash  = SHA256(encryptedBodyHex)
signature = HMAC-SHA256(hmacKey, "POST\n" + path + "\n" + timestamp + "\n" + nonce + "\n" + bodyHash)
// 五头：X-Session-ID / X-Timestamp / X-Nonce / X-Signature / X-Key-Version: 1
```

3. **响应解密**：响应 `{data, nonce, key_mode, version, ...}` 用同一 aesKey 解密；`key_mode == "chapter"` 时换章节密钥（见 §3）。

### 2.3 Rhino 实现要点

- `Packages.javax.crypto.Cipher` + `GCMParameterSpec(128, iv)` —— **SunJCE 拒绝用 IvParameterSpec 走 GCM**，必须 GCMParameterSpec。
- `Packages.javax.crypto.Mac` + `SecretKeySpec` 做 HMAC/HKDF。
- `Packages.java.security.MessageDigest.getInstance("SHA-256")` 做摘要。
- 随机数生成用 `KeyGenerator.getInstance("AES")` 生成后取 encode 字节（`java.randomBytes` 不总是可用）。
- **字节收窄**：Rhino 里 `byte & 255` 后写回要 `w > 127 ? w - 256 : w`，否则 `Cannot convert 151 to java.lang.Byte`。
- **base64**：`java.base64Encode` 会按 UTF-8 损坏二进制 → **手写 base64**（表 `A-Za-z0-9+/`，逐 3 字节）。

---

## 3. 章节正文本地解密（key_mode=chapter）★核心

正文响应 `key_mode=chapter` 时，**不是**用会话 aesKey 解密，而是按章重派生：

```js
chapterKey = HKDF(key_material,
                  salt = book_id + "\n" + chapter_id + "\n" + version + nonce,
                  info = "novel-chapter-aes-v1",
                  len  = 32)
plain = AES-256-GCM-Decrypt(chapterKey, nonce, data)
```

关键点：

1. **站点原本用 WASM 模块做这件事** —— 我们完全绕开：HKDF 是标准算法，`key_material` 已在 bootstrap 拿到，纯 JS/Java 就能重派生。**遇到 WASM 解密模块不要逆向 WASM，先找协议里的密钥材料。**
2. salt 里的 `version + nonce` 来自**响应体字段**（`a.version`, `a.nonce`），拼接时 nonce 用原始字节（hex 后再转回）。
3. 结果 `{paragraphs:[{text}...]}` 直接拼 `\n\n` 成正文。

---

## 4. Legado 规则传参技巧：bootstrap GET 携参 ★核心

**痛点**：搜索/详情/目录/正文全是 POST，Legado 的规则链只传 URL 字符串，业务参数（book_id/chapter_id）没有地方放。

**解法**：把参数藏进一个无害的 GET 地址 query 里，各规则从 `baseUrl` 里取回：

```js
// 生成：zjUrl('zjb', bookId) → https://www.zjread.cc/api/bootstrap?zjb=12345
// 取回：zjParam(baseUrl, 'zjb') → '12345'
function zjUrl(k, v){ return ZJ_BASE + '/api/bootstrap?' + k + '=' + encodeURIComponent(v) }
function zjParam(url, k){ var m = String(url).match(new RegExp('[?&]' + k + '=([^&]+)')); return m ? decodeURIComponent(m[1]) : '' }
```

- 搜索：`searchUrl = BASE + '/api/bootstrap?zjk=' + key + '&zjp=' + page`
- 详情：`bookUrl = zjUrl('zjb', id)`；`tocUrl` 同样携 `zjb`
- 正文：`chapterUrl = zjUrl('zjc', chapterId)`
- 封面同理（`/api/cover?...&data=加密串`）

**通用性**：任何「规则字段是 POST/需要参数但 Legado 无法直接传」的站都可以用这个套路，选一个站点本来就存在的 GET 路径当载体，不会 404、不惹眼。

---

## 5. 字段预取缓存：ruleBookInfo.init 一次取详情

详情页有 8 个字段（name/author/intro/kind/lastChapter/coverUrl/...），若每个字段各自 `@js` 发一次请求 = 8 次请求 + 8 次解密。

解法：`init` 里一次性取详情、算好全部字段、塞进 `java.put` 缓存，其余字段只读缓存：

```js
// init
var d = JSON.parse(zjPost('/api/book/detail', {book_id: id}));
java.put('zjd', JSON.stringify({name, author, kind, intro, coverUrl, ...}));
// 其它字段
"name": "@js:zjInit(java,source);(JSON.parse(java.get('zjd')||'{}'))['name']||''"
```

同理会话缓存（`source.put('zj_session_v1', ...)`）与 token 缓存（§1.3）。

---

## 6. 错误分流：retry（换会话）vs verify（清 token）

统一错误分类，每类各重试 2 次，避免死循环：

| 错误 | 判定 | 处理 |
|------|------|------|
| 会话/签名被拒 | HTTP 401 / code 401 / 请求异常 | `retry: true` → 丢弃会话缓存，重新 bootstrap |
| 人机验证未过 | HTTP 403 / code 403/4001 | `verify: true` → 清 captcha_token 缓存，重新挑战 |
| 业务错误 | code≠0 其它 | 直接抛错，不重试 |

```js
for (var i = 0; i < 2; i++) {
  var s = getSession(1 === i);          // 第 2 次强制刷新会话
  try { token = getCaptcha(s) } catch(e) { clearToken(); continue }
  var r = post(s, '/api/book/content', {chapter_id, captcha_token: token});
  if (r.plain !== undefined) return render(r.plain);
  if (r.verify) clearToken();           // 下一轮重新解验证码
  if (!r.retry && !r.verify) throw r.err;
}
```

---

## 7. 调试踩坑记录（血泪）

1. **`Packages.*` 不是全都能用**：真机报 `无法调用对象 [JavaPackage java.lang.reflect.Array]` → Legado 对部分包做了限制。用 `strToBytes/bytesToStr/hexDecodeToByteArray` 等 java.* 原生方法替代反射。
2. **bookList 必须返回「字符串数组」**：直接返回 NativeObject 数组会 `ClassCastException: String cannot be cast to List`；每个元素 `JSON.stringify(obj)` 成字符串，字段规则再用 `$.field` 读。
3. **jsLib 作用域没有 `java`/`source`**：jsLib 在独立 SharedJsScope 执行（空绑定）→ 库函数用 `zjInit(java, source)` 由规则入口显式注入，不要依赖全局。
4. **Java 字符串与 JS 字面量 `===` 永假**：`h === '__ZJ_VERIFY__'` 永远 false（跨语言包装）→ 用 `String(h).indexOf('__ZJ_VERIFY__') >= 0`。
5. **`java.webView` 的 js 参数会被 Legado 自动重试**（约 30 次/28 秒）：自己在 js 里 `setTimeout` 轮询 + 返回 null 会与自动重试打架 → 页面注入函数写成「同步单次检查，未就绪就返回 null」，把重试交给 Legado。
6. **WebView 里 CF 盾验证失败**：Legado WebView 默认桌面 UA 与 CF 的 Android 检测冲突 → 注入真实 Android Chrome UA。
7. **CF 验证是「按会话」的**：浏览器里全程只过 1 次盾（0 次 bootstrap），因为 Cookie/会话在服务端标记。→ WebView 过盾后要**共享会话**（同一 webView 实例 + 注入页面复用），不要每章重开。
8. **目录太大别硬解密**：500KB 加密目录在 Rhino 里解密超时 → 目录改走 WebView 提取 DOM（`.chapter-list`），或直接调目录接口取精简 JSON。
9. **AES-GCM 的 GHASH 长度块是 16 字节**（8 字节 AAD 位长 + 8 字节密文位长），且是对**密文**做 GHASH，不是明文——纯 JS 回退实现时的经典坑。
10. **`java.base64Encode` 按 UTF-8 处理** → 二进制数据被损坏；纯 JS base64 才安全。

---

## 8. 复用清单（遇到下一个加密 API 站时按此顺序）

1. 打开页面 → 保存首页 HTML → 找主 JS bundle → 搜 `bootstrap`/`/api/`/`encrypt`/`captcha`。
2. 找到 bootstrap 接口，抓一次响应：找 `session_id`、`key_material`。
3. 搜 JS 里 `info:"..."` 字符串（如 `novel-api-aes-v1`）→ 确认 HKDF 的 info/salt 用法。
4. 找请求签名：搜 `X-Signature`/`X-Nonce` 或 HMAC 调用点 → 复刻签名字符串。
5. 找响应解密：确认 `key_mode` 分支（session/chapter）→ 章节模式找 salt 拼接公式。
6. 找验证码：搜 `captcha`/`altcha`/`challenge` → 若是 PoW 类，本地实现求解器。
7. 用 Python 先验证协议（快），再把逻辑移植进 jsLib（Rhino 限制多）。
8. Legado 传参用 §4 技巧；字段预取用 §5；错误分流用 §6。

# API 发现三步法（JSON 接口型站点）

适用：搜索/目录/正文靠 XHR 接口返回 JSON 的站。**核心原则：不要猜测 URL 格式，从页面 JS 里找真实 API。**

> 进阶：如果接口**被加密签名**（请求带 `X-Signature` 等头）、**响应是密文**（`{data,nonce}`）、或**接口 403 但页面无验证码组件**，属于「加密 API 站」，走三步法找到接口后还需复刻协议——见 `references/encrypted-api-altcha.md`（bootstrap→HKDF→AES-GCM+HMAC、ALTCHA 本地 PoW 免人工验证、章节本地解密、bootstrap 携参技巧）。

## 为什么不能瞎猜

```python
# ❌ 效率极低，成功率趋近于零
search_urls = ['/search.php?q=', '/api/search?q=', '/search?keyword=']
```

## 三步法

**第一步**：抓首页 HTML，列出所有外部 JS：

```python
import requests, re
html = requests.get('https://www.example.com', headers=UA).text
js_files = re.findall(r'<script[^>]*src=["\']([^"\']+\.js[^"\']*)["\']', html)
```

**第二步**：逐个下载 JS，搜 API 调用模式：

```python
api_patterns = [
    r'\$\.ajax\(\s*["\']([^"\']+)["\']',
    r'\$\.get\(\s*["\']([^"\']+)["\']',
    r'\$\.post\(\s*["\']([^"\']+)["\']',
    r'getJSON\(\s*["\']([^"\']+)["\']',
    r'fetch\(\s*["\']([^"\']+)["\']',
]
for js_url in js_files:
    js = requests.get(urllib.parse.urljoin(base, js_url)).text
    for p in api_patterns:
        for m in re.findall(p, js):
            print('发现API:', m)
```

**第三步**：用真实参数测试发现的 API，确认返回 JSON 的结构（列表字段、分页参数）。

## 实战案例：笔趣阁 bqgui

1. 正文页有验证机制 → 转向分析 JS：`https://www.bqgui.cc/js/compc.js?v=1.23`
2. 正则 `getJSON\(["\']([^"\']+)["\']` 命中 `/json_book?id=`
3. 测试 `https://www.bqgui.cc/json_book?id=66` → 返回章节 JSON ✅
4. 书源用 JSONPath 规则（`$.` 前缀）对接。

## 实战案例：纸间 zjread（全加密协议站）

1. 首页是 SPA 壳，业务全在 `/assets/index-*.js` bundle 里。
2. 搜 `bootstrap` 找到 `GET /api/bootstrap` → 响应含 `session_id` + `key_material`。
3. 搜 `info:` 字符串（`novel-api-aes-v1` 等）→ 确认 HKDF 派生参数；搜 `X-Signature` 找签名拼接公式。
4. 搜 `captcha`/`altcha` → 发现隐藏的 PoW 验证接口（本地求解换 token，免人工）。
5. 完整复刻记录见 `legadoSkill/assets/zjread技术笔记.md`；书源成品 `zjread.json参考.txt`。

## 核心技巧

1. **分析而不是猜测**——先看 JS 再动手。
2. **备用域名也有 API**——主域名被验证挡住时，分析备用域名的 JS，常有惊喜。
3. **从验证页提取备用域名**并存进书源变量：

```js
var html = java.webView(url, url, 'setTimeout(function(){window.legado.getHTML(document.documentElement.outerHTML);},5000);');
var match = html.match(/https?:\/\/([\w\-\.]+)\//);
if (match) { source.setVariable(match[1]); }
```

4. 有些 API 需要特殊请求头（Referer/X-Requested-With）或 Cookie——在 option 的 `headers` 里带上。
5. API 型站点的分页通常是 `page` 或 `offset` 参数，用 `{{page}}` 注入；返回 JSON 里找 `total`/`has_more` 判断是否还有下一页。

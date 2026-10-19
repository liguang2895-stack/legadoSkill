// rhino_harness.js — 规则级真引擎验证台（validator 误报/受限时的替代证据）
//
// 用途：用 validator JAR 自带的真 Rhino 引擎（与 Legado 同引擎）直接跑单条规则 JS，
//       验证 API 型目录/搜索/正文规则的真实行为（网络、加密、排序、去重）。
//
// 用法（在 SKILL_DIR 下）：
//   java -cp validator/app/legado-source-validator.jar \
//        org.mozilla.javascript.tools.shell.Main scripts/rhino_harness.js <rule.js> [<page.html>] [<baseUrl>]
//
//   参数：
//     rule.js   — 待测规则 JS（从书源 JSON 的 "@js:" 后提取；若是 HTML 类规则可传占位）
//     page.html — （可选）规则里 result 变量的初始值来源（如详情页 HTML）
//     baseUrl   — （可选）baseUrl 变量；默认取 page.html 里的 og:url 或传参
//
//   规则 JS 里可用的全局：java（真实模拟 Legado）、result、baseUrl、key、page
//
// Legado 行为模拟点（与真机一致的近似）：
//   - java.ajax(url) / java.ajax("url,{options}")：URL+options 时 POST 走 form 编码
//     （等价 AnalyzeUrl.analyzeFields：k + "=" + URLEncoder.encode(v)）
//   - java.createSymmetricCrypto：真 javax.crypto（AES/CBC/PKCS5Padding）
//   - java.base64Decode / java.log：真实现
//
// 输出：规则返回值写入 stdout（前缀 HARNESS_RESULT:），便于脚本断言。

var UA = 'Mozilla/5.0 (Linux; Android 13; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36';

function readText(path) {
    return String(java.nio.file.Files.readString(
        java.nio.file.Paths.get(path), java.nio.charset.StandardCharsets.UTF_8));
}
function readAll(stream) {
    var reader = new java.io.BufferedReader(new java.io.InputStreamReader(stream, "UTF-8"));
    var sb = new java.lang.StringBuilder();
    var line;
    while ((line = reader.readLine()) !== null) { sb.append(line); sb.append("\n"); }
    reader.close();
    return String(sb.toString());
}
function httpGet(url) {
    var conn = new java.net.URL(url).openConnection();
    conn.setRequestProperty("User-Agent", UA);
    conn.setConnectTimeout(20000);
    conn.setReadTimeout(20000);
    return readAll(conn.getInputStream());
}
function httpPostForm(url, body) {
    var conn = new java.net.URL(url).openConnection();
    conn.setRequestMethod("POST");
    conn.setDoOutput(true);
    conn.setRequestProperty("User-Agent", UA);
    conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8");
    conn.setConnectTimeout(20000);
    conn.setReadTimeout(20000);
    var os = conn.getOutputStream();
    os.write(new java.lang.String(body).getBytes("UTF-8"));
    os.flush(); os.close();
    return readAll(conn.getInputStream());
}
// 等价 Legado AnalyzeUrl.analyzeFields：'data=RAW' -> 'data=' + URLEncoder.encode(RAW)
function formEncode(body) {
    var eq = body.indexOf("=");
    if (eq < 0) return String(body);
    var k = body.substring(0, eq);
    var v = body.substring(eq + 1);
    return k + "=" + String(java.net.URLEncoder.encode(v, "UTF-8"));
}
function doAjax(urlStr) {
    var s = String(urlStr);
    var idx = s.lastIndexOf(",{");
    if (idx >= 0) {
        var base = s.substring(0, idx);
        var optStr = s.substring(idx + 1);
        var opt = JSON.parse(optStr);
        if (opt.method && String(opt.method).toUpperCase() === "POST") {
            return httpPostForm(base, formEncode(String(opt.body || "")));
        }
    }
    return httpGet(s);
}
function aesEncryptBase64(transformation, keyStr, ivStr, dataStr) {
    var keyBytes = new java.lang.String(String(keyStr)).getBytes("UTF-8");
    var ivBytes = new java.lang.String(String(ivStr)).getBytes("UTF-8");
    var dataBytes = new java.lang.String(String(dataStr)).getBytes("UTF-8");
    var cipher = javax.crypto.Cipher.getInstance(String(transformation));
    cipher.init(javax.crypto.Cipher.ENCRYPT_MODE,
        new javax.crypto.spec.SecretKeySpec(keyBytes, "AES"),
        new javax.crypto.spec.IvParameterSpec(ivBytes));
    var out = cipher.doFinal(dataBytes);
    return String(java.util.Base64.getEncoder().encodeToString(out));
}
var javaMock = {
    ajax: function (url) { return doAjax(url); },
    log: function (msg) { print("[java.log] " + msg); },
    base64Decode: function (s) {
        var bytes = java.util.Base64.getDecoder().decode(String(s));
        return String(new java.lang.String(bytes, "UTF-8"));
    },
    createSymmetricCrypto: function (transformation, keyStr, ivStr) {
        return {
            encryptBase64: function (data) {
                return aesEncryptBase64(transformation, keyStr, ivStr, data);
            }
        };
    }
};

// ---- main ----
// ★ 不要用 "var java = javaMock" 覆盖全局 java 包——会破坏上面 helper 里的 java.* 调用。
// 用函数参数注入：规则在 runRule 作用域里 eval，java 解析为参数（mock），全局 java 包不受影响。
function runRule(java, result, baseUrl, key, page, src) {
    return eval(src);
}

var args = typeof arguments !== 'undefined' ? arguments : [];
var rulePath = args[0];
if (!rulePath) {
    print("用法: Main rhino_harness.js <rule.js> [<page.html>] [<baseUrl>]");
    quit(2);
}
var pagePath = args[1] || "";
var baseUrl = args[2] || "";

var ruleSrc = readText(String(rulePath));
var result = pagePath ? readText(String(pagePath)) : "";
if (!baseUrl && pagePath) {
    var m = String(result).match(/og:url" content="([^"]+)"/);
    baseUrl = m ? String(m[1]) : "";
}

var key = "";
var page = 1;
var out = runRule(javaMock, result, baseUrl, key, page, ruleSrc);
print("HARNESS_RESULT:" + (out === null || out === undefined ? "null" : String(out)));

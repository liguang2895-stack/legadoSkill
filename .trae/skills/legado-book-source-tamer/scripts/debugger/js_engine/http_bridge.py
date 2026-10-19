#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
http_bridge.py — JS 引擎 HTTP 桥

被 js_engine 的 Node shim 以子进程方式调用，执行真实 HTTP 请求并回传完整响应
（含真实状态码），供 java.ajax / java.connect / java.post / java.head 使用。

协议：stdin 收 JSON 请求，stdout 回 JSON 响应。
    in : {"action":"ajax|connect|post|head", "url":..., "headers":{...},
          "body":"...", "charset":"...", "timeout":30}
    out: {"ok":bool, "url":..., "code":int, "body":str, "headers":{...},
          "error":str|null}
"""

import io
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import gzip
import zlib

if sys.platform == "win32":
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _decode(content: bytes, charset: str, headers) -> str:
    if charset:
        try:
            return content.decode(charset)
        except Exception:
            pass
    ctype = ""
    try:
        ctype = headers.get("Content-Type", "") or ""
    except Exception:
        pass
    if "charset=" in ctype.lower():
        enc = ctype.lower().split("charset=")[-1].split(";")[0].strip()
        try:
            return content.decode(enc)
        except Exception:
            pass
    for enc in ("utf-8", "gbk", "gb18030", "latin-1"):
        try:
            return content.decode(enc)
        except Exception:
            continue
    return content.decode("utf-8", errors="replace")


def main():
    raw = sys.stdin.read()
    try:
        req = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"bad request json: {e}"},
                         ensure_ascii=False))
        return 1

    url = req.get("url") or ""
    if not url:
        print(json.dumps({"ok": False, "error": "missing url"}, ensure_ascii=False))
        return 1

    action = req.get("action") or "ajax"
    headers = req.get("headers") or {}
    body = req.get("body")
    charset = req.get("charset") or ""
    timeout = float(req.get("timeout") or 30)

    if isinstance(body, str):
        body = body.encode("utf-8")

    data = body if action == "post" else None
    if action == "head":
        method = "HEAD"
    elif action == "post":
        method = "POST"
    else:
        method = "GET"

    # 默认浏览器 UA（与阅读 HttpHelper 默认一致）
    hdrs = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }
    for k, v in (headers or {}).items():
        hdrs[str(k)] = str(v)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        with urllib.request.urlopen(request, timeout=timeout, context=ctx) as resp:
            content = resp.read()
            code = resp.status
            resp_headers = dict(resp.headers)
            enc = (resp.headers.get("Content-Encoding") or "").lower()
            if "gzip" in enc or content[:2] == b"\x1f\x8b":
                try:
                    content = gzip.decompress(content)
                except Exception:
                    pass
            elif "deflate" in enc:
                try:
                    content = zlib.decompress(content, -zlib.MAX_WBITS)
                except Exception:
                    pass
        print(json.dumps({
            "ok": True, "url": url, "code": code,
            "body": _decode(content, charset, resp_headers),
            "headers": {k: v for k, v in resp_headers.items()},
            "error": None,
        }, ensure_ascii=False))
        return 0
    except urllib.error.HTTPError as e:
        try:
            content = e.read()
            text = _decode(content, charset, e.headers or {})
        except Exception:
            text = ""
        print(json.dumps({
            "ok": False, "url": url, "code": e.code, "body": text,
            "headers": dict(e.headers or {}), "error": f"HTTP {e.code}",
        }, ensure_ascii=False))
        return 0
    except Exception as e:
        print(json.dumps({
            "ok": False, "url": url, "code": 0, "body": "",
            "headers": {}, "error": str(e),
        }, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verify_source.py — 书源真引擎验证 + 交付门禁（L2）

用内嵌 Kotlin validator（Legado 规则引擎等价实现）跑真实四链路：
    搜索 → 详情 → 目录 → 正文

产出的 verify-report.json 是交付话术的唯一依据：
- 报告由脚本生成，AI 不得手写或改写结论
- 报告带 _sourceHash；源文件改动后旧报告自动失效
- 交付前用 --check 复核报告与当前源文件是否匹配

用法（在 SKILL_DIR/scripts 下执行）：
    python verify_source.py <书源.json> -k "关键词"           # 完整验证
    python verify_source.py <书源.json> -k "关键词" --book-url <url>  # 跳过搜索
    python verify_source.py <书源.json> --check               # 交付前复核报告有效性

退出码：
    0 = passed（报告有效，可交付）
    2 = partial/degraded（只能按降级话术交付）
    1 = failed / blocked / 报告失效
"""

import argparse
import hashlib
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    if not (isinstance(sys.stdout, io.TextIOWrapper)
            and (sys.stdout.encoding or "").lower().startswith("utf-8")):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if not (isinstance(sys.stderr, io.TextIOWrapper)
            and (sys.stderr.encoding or "").lower().startswith("utf-8")):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import validator_run  # noqa: E402
import rule_audit  # noqa: E402

REPORT_NAME = "verify-report.json"

# errorCode → blocker 分类（移植 book-source-creator-skill 的 ERROR_CODE_BLOCKER）
ERROR_CODE_BLOCKER = {
    "CAPTCHA_DETECTED": "captcha",
    "CONTENT_IS_CAPTCHA_PAGE": "captcha",
    "CONTENT_IS_VIP_LOCK_PAGE": "vip",
    "CONTENT_IS_LOGIN_PAGE": "login",
    "COOKIE_REQUIRED": "login",
    "COOKIE_PRESENT_BUT_UNAUTHORIZED": "login",
    "CONTENT_IS_CSR_SHELL": "csr",
    "CHAPTER_URL_MISSING_WEBVIEW": "csr",
    "WEBVIEW_RENDER_TIMEOUT": "csr",
    "WEBJS_RETURN_EMPTY": "csr",
    "WEBJS_EXEC_ERROR": "csr",
}

# blocker → 处置纪律（交付说明必须遵守）
BLOCKER_POLICY = {
    "captcha": "站点验证码/人机验证。禁止换关键词或换 mode 反复重试（会累积 IP 风控）；"
               "让用户手动过验证或按失败如实交付。",
    "cloudflare": "Cloudflare/反爬拦截。App 同样会被拦，这是站点固有限制，按失败交付。",
    "vip": "付费/VIP 限制。免费章节能力可交付，但必须标注 degraded，不得写 full pass。",
    "login": "需要登录态。检查 loginUrl/enabledCookieJar/java.getCookie 三件套；"
             "无法登录则如实标注。",
    "csr": "正文/页面依赖 WebView 渲染或 JS 执行。本地 HTTP 验证不可达，"
           "需在 Legado App 内实测确认，交付时必须标注未验证。",
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _post_json(url: str, payload: dict, timeout: int = 180) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _step_blocker(step: dict) -> str:
    code = step.get("errorCode") or ""
    if code in ERROR_CODE_BLOCKER:
        return ERROR_CODE_BLOCKER[code]
    if code == "HTTP_BLOCKED":
        preview = str((step.get("response") or {}).get("bodyPreview", "")).lower()
        if "cloudflare" in preview or "just a moment" in preview or "turnstile" in preview:
            return "cloudflare"
        return "network"
    return ""


def _acceptance(phases: dict, summary: dict, steps: list) -> list:
    """验收标准（移植 validation-policy.md）：逐条给出 pass/fail 与依据。"""
    checks = []

    def _add(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    # search
    rc = summary.get("resultCount", 0)
    _add("search 有结果", phases.get("search") == "success" and rc >= 1,
         f"status={phases.get('search')}, resultCount={rc}")

    # detail
    detail_ok = phases.get("detail") == "success"
    detail_name = ""
    for s in steps:
        if s.get("phase") == "detail" and s.get("extracted"):
            detail_name = s["extracted"].get("name", "")
            break
    _add("detail 有书名", detail_ok and bool(detail_name),
         f"status={phases.get('detail')}, name={detail_name!r}")

    # toc
    cc = summary.get("chapterCount", 0)
    _add("toc 有章节", phases.get("toc") == "success" and cc >= 1,
         f"status={phases.get('toc')}, chapterCount={cc}")
    if 0 < cc < 10:
        checks.append({"check": "toc 章节数偏少", "pass": True,
                       "detail": f"仅 {cc} 章——需人工确认是新书/短篇，"
                                 f"而不是目录规则只取到局部"})

    # content
    content_len = 0
    for s in steps:
        if s.get("phase") == "content" and s.get("extracted"):
            content_len = max(content_len, s["extracted"].get("contentLength", 0))
    _add("content 正文足够长", phases.get("content") == "success" and content_len >= 100,
         f"status={phases.get('content')}, contentLength={content_len}")

    return checks


def _overall_status(phases: dict, acceptance: list, blocker: str) -> str:
    if blocker in ("captcha", "cloudflare"):
        return "blocked"
    passed = all(c["pass"] for c in acceptance if "偏少" not in c["check"])
    if passed and phases.get("content") == "success":
        return "passed"
    any_success = any(v == "success" for v in phases.values())
    if any_success:
        return "partial"
    return "failed"


def _load_cookie_entries(cookie_arg: str, source_url: str) -> list:
    """解析 --cookie 参数，支持两种格式：
    - curl cookie jar 文件（Netscape 格式，curl -c 生成）
    - JSON 文件：{"www.example.com": "a=b; c=d"} 或 {"domain":"...","cookie":"..."}
    返回 [{"domain": ..., "cookie": ...}, ...]
    """
    try:
        text = Path(cookie_arg).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise ValueError(f"Cookie 文件无法读取: {cookie_arg} ({e})") from e
    stripped = text.strip()
    entries = []

    # JSON 格式
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "domain" in data and "cookie" in data:
                return [{"domain": data["domain"], "cookie": data["cookie"]}]
            if isinstance(data, dict):
                for domain, cookie in data.items():
                    if isinstance(cookie, str):
                        entries.append({"domain": domain, "cookie": cookie})
                return entries
        except json.JSONDecodeError:
            pass

    # Netscape cookie jar
    by_domain = {}
    for line in stripped.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            domain = parts[0].lstrip(".")
            by_domain.setdefault(domain, []).append(f"{parts[5]}={parts[6]}")
    for domain, pairs in by_domain.items():
        entries.append({"domain": domain, "cookie": "; ".join(pairs)})
    return entries


def _inject_cookies(url: str, cookie_arg: str, source_url: str) -> list:
    entries = _load_cookie_entries(cookie_arg, source_url)
    injected = []
    for e in entries:
        try:
            _post_json(f"{url}/api/cookie/set", e, timeout=15)
            injected.append(e["domain"])
        except Exception as ex:
            print(f"[warn] Cookie 注入失败 {e['domain']}: {ex}", file=sys.stderr)
    return injected


def run_verify(source_path: Path, keyword: str, book_url: str = "",
               cookie_file: str = "") -> dict:
    raw = source_path.read_text(encoding="utf-8")
    source_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    data = json.loads(raw)
    sources = data if isinstance(data, list) else [data]
    first = sources[0] if sources else {}
    source_url = first.get("bookSourceUrl", "")

    report = {
        "_generatedBy": "verify_source.py",
        "_schemaVersion": "1.0",
        "_sourceHash": source_hash,
        "sourcePath": str(source_path),
        "sourceUrl": source_url,
        "keyword": keyword,
        "mode": "http",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "engine": "legado-source-validator (embedded, Kotlin)",
    }

    # L1 静态审计
    audit_report = rule_audit.audit(first, source_hash)
    report["staticAudit"] = {
        "status": audit_report["status"],
        "errors": audit_report["errors"],
        "warnings": audit_report["warnings"],
    }
    if audit_report["status"] != "passed":
        report["status"] = "failed"
        report["reason"] = "静态审计未通过，未进入真引擎验证"
        report["acceptance"] = []
        return report

    # L2 真引擎验证
    url, err = validator_run.ensure_running()
    if not url:
        report["status"] = "error"
        report["reason"] = f"validator 不可用: {err}"
        report["acceptance"] = []
        return report
    report["validatorUrl"] = url

    # 可选：注入 Cookie（需要登录态或反爬预热的站点）
    if cookie_file:
        try:
            injected = _inject_cookies(url, cookie_file, source_url)
        except ValueError as e:
            report["status"] = "error"
            report["reason"] = str(e)
            report["acceptance"] = []
            return report
        report["injectedCookieDomains"] = injected
        if not injected:
            report["status"] = "error"
            report["reason"] = f"Cookie 文件无法解析出任何域: {cookie_file}"
            report["acceptance"] = []
            return report

    payload = {
        "sourceJson": json.dumps(sources, ensure_ascii=False),
        "sourceUrl": source_url,
        "keyword": keyword,
        "mode": "http",
    }
    if book_url:
        payload["bookUrl"] = book_url

    try:
        resp = _post_json(f"{url}/api/debug/run", payload)
    except Exception as e:
        report["status"] = "error"
        report["reason"] = f"调用 validator 失败: {e}"
        report["acceptance"] = []
        return report

    phases = resp.get("phases") or {}
    summary = resp.get("summary") or {}
    steps = resp.get("steps") or []

    # 精简 steps，保留诊断关键字段
    slim_steps = []
    first_blocker = ""
    for s in steps:
        blocker = _step_blocker(s)
        if blocker and not first_blocker:
            first_blocker = blocker
        slim_steps.append({
            "phase": s.get("phase"),
            "status": s.get("status"),
            "error": s.get("error"),
            "errorCode": s.get("errorCode"),
            "failedField": s.get("failedField"),
            "blocker": blocker,
            "request": s.get("request"),
            "responseCode": (s.get("response") or {}).get("code"),
            "bodyPreview": (s.get("response") or {}).get("bodyPreview", "")[:300],
            "extracted": s.get("extracted"),
            "ruleHits": [
                {"field": h.get("field"), "rule": h.get("rule"),
                 "success": h.get("success"), "value": str(h.get("value"))[:120]}
                for h in (s.get("ruleHits") or [])
            ],
        })

    acceptance = _acceptance(phases, summary, steps)
    status = _overall_status(phases, acceptance, first_blocker)
    if first_blocker == "vip" and status == "partial":
        status = "degraded"

    report.update({
        "status": status,
        "finalStatusFromValidator": resp.get("finalStatus"),
        "phases": phases,
        "summary": {
            "resultCount": summary.get("resultCount", 0),
            "firstBook": summary.get("firstBook", ""),
            "chapterCount": summary.get("chapterCount", 0),
            "contentPreview": str(summary.get("contentPreview", ""))[:200],
        },
        "blocker": first_blocker,
        "blockerPolicy": BLOCKER_POLICY.get(first_blocker, ""),
        "acceptance": acceptance,
        "steps": slim_steps,
    })

    if first_blocker == "csr":
        report["status"] = "partial" if status == "passed" else status
        report["reason"] = (report.get("reason") or "") + \
            "正文依赖 WebView/JS，本地 HTTP 验证不完整，需 App 实测"
    return report


def cmd_check(source_path: Path) -> int:
    """交付前复核：报告是否存在、是否对应当前源文件、状态是否可交付。"""
    report_path = source_path.parent / REPORT_NAME
    if not report_path.exists():
        print(json.dumps({
            "ok": False,
            "error": f"未找到验证报告: {report_path}",
            "nextCommand": f'python verify_source.py "{source_path}" -k "<关键词>"',
            "message": "交付前必须运行真引擎验证。没有报告 = 未验证。",
        }, ensure_ascii=False, indent=2))
        return 1

    report = json.loads(report_path.read_text(encoding="utf-8"))
    current_hash = _sha256_file(source_path)
    if report.get("_sourceHash") != current_hash:
        print(json.dumps({
            "ok": False,
            "error": "报告已失效：书源文件在验证后被修改",
            "reportHash": report.get("_sourceHash"),
            "currentHash": current_hash,
            "nextCommand": f'python verify_source.py "{source_path}" -k "<关键词>"',
            "message": "源文件已改动，旧验证结论作废，必须重新验证。",
        }, ensure_ascii=False, indent=2))
        return 1

    status = report.get("status")
    deliverable = status in ("passed", "partial", "degraded")
    result = {
        "ok": deliverable,
        "status": status,
        "sourceHash": current_hash,
        "phases": report.get("phases"),
        "blocker": report.get("blocker", ""),
        "acceptance": report.get("acceptance", []),
        "verifiedAt": report.get("timestamp"),
    }
    if status == "passed":
        result["deliveryNote"] = "可交付。交付说明引用本报告状态；提醒用户在 Legado App 实测。"
    elif status in ("partial", "degraded"):
        result["deliveryNote"] = ("只能按降级话术交付：明确列出未通过/降级的链路，"
                                  "禁止写「全链路可用」「full pass」。")
    else:
        result["deliveryNote"] = ("不可交付。按报告 blocker 与 acceptance 修复后重新验证，"
                                  "或如实告知用户站点限制。")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status == "passed" else (2 if deliverable else 1)


def _print_human(report: dict):
    print("=" * 60)
    print(" 书源真引擎验证（搜索 → 详情 → 目录 → 正文）")
    print("=" * 60)
    print(f"源文件: {report.get('sourcePath')}")
    print(f"状态: {report.get('status')}")
    print(f"关键词: {report.get('keyword')}")
    print()
    phases = report.get("phases") or {}
    if phases:
        for p in ("search", "detail", "toc", "content"):
            print(f"  {p:8s}: {phases.get(p, 'unknown')}")
    print()
    if report.get("blocker"):
        print(f"阻塞类型: {report['blocker']}")
        print(f"处置纪律: {report.get('blockerPolicy')}")
        print()
    acc = report.get("acceptance") or []
    if acc:
        print("验收标准:")
        for c in acc:
            mark = "✓" if c["pass"] else "✗"
            print(f"  {mark} {c['check']} ({c['detail']})")
        print()
    if report.get("reason"):
        print(f"说明: {report['reason']}")
    if report.get("staticAudit", {}).get("errors"):
        print("\n静态审计错误:")
        for e in report["staticAudit"]["errors"]:
            print(f"  ✗ {e['message']}")


def main():
    parser = argparse.ArgumentParser(description="书源真引擎验证与交付门禁")
    parser.add_argument("source", help="书源 JSON 文件")
    parser.add_argument("-k", "--keyword", default="", help="搜索关键词")
    parser.add_argument("--book-url", default="",
                        help="跳过搜索，直接从书籍 URL 开始验证（搜索被反爬阻塞时用）")
    parser.add_argument("--cookie", default="",
                        help="Cookie 文件（curl -c 生成的 jar 或 JSON），"
                             "用于需要登录态/反爬预热的站点")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    parser.add_argument("--check", action="store_true",
                        help="交付前复核已有报告（不重新验证）")
    parser.add_argument("--report", default="",
                        help=f"报告输出路径（默认源文件同目录 {REPORT_NAME}）")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"文件不存在: {source_path}", file=sys.stderr)
        return 1

    if args.check:
        return cmd_check(source_path)

    if not args.keyword and not args.book_url:
        print("必须提供 -k 关键词（或 --book-url 跳过搜索）", file=sys.stderr)
        return 1

    report = run_verify(source_path, args.keyword, args.book_url, args.cookie)

    report_path = Path(args.report) if args.report else source_path.parent / REPORT_NAME
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
        print(f"\n报告已写入: {report_path}")

    status = report.get("status")
    if status == "passed":
        return 0
    if status in ("partial", "degraded"):
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())

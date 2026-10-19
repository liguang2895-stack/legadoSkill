#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
rule_audit.py — 书源静态规则审计（交付门禁 L1）

移植 book-source-creator-skill 的 official-rule-pack 检查 + 本技能 pitfalls.md 检查项。
纯静态审计，不发网络请求，不模拟 Legado 执行；通过 ≠ 可用，只代表没有已知静态错误。

用法（在 SKILL_DIR/scripts 下执行）：
    python rule_audit.py <书源.json>            # 人类可读报告
    python rule_audit.py <书源.json> --json     # 机器可读 JSON 报告

退出码：0 = 通过（无 error）；1 = 有 error；2 = 文件/用法错误
"""

import argparse
import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    if not (isinstance(sys.stdout, io.TextIOWrapper)
            and (sys.stdout.encoding or "").lower().startswith("utf-8")):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if not (isinstance(sys.stderr, io.TextIOWrapper)
            and (sys.stderr.encoding or "").lower().startswith("utf-8")):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SKILL_DIR = Path(__file__).resolve().parent.parent
RULE_PACK_PATH = SKILL_DIR / "references" / "official-rule-pack.json"

RULE_GROUPS = ["ruleSearch", "ruleExplore", "ruleBookInfo", "ruleToc", "ruleContent"]

# 模板占位符（AI 生成后未替换的真实规则）
PLACEHOLDER_TEXT = {
    "书籍列表规则", "书名规则", "作者规则", "封面规则", "详情页URL规则", "简介规则",
    "分类规则", "最新章节规则", "字数规则", "目录URL规则", "章节列表规则",
    "章节名称规则", "章节URL规则", "目录下一页规则", "正文内容规则",
    "正文下一页规则", "搜索URL规则",
}

# 必填字段（对齐 Legado BookSource 结构）
REQUIRED_TOP = ["bookSourceUrl", "bookSourceName", "searchUrl",
                "ruleSearch", "ruleBookInfo", "ruleToc", "ruleContent"]
REQUIRED_NESTED = {
    "ruleSearch": ["bookList", "name", "bookUrl"],
    "ruleBookInfo": ["name"],
    "ruleToc": ["chapterList", "chapterName", "chapterUrl"],
    "ruleContent": ["content"],
}


def _is_blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _is_json_or_js_rule(value: str) -> bool:
    """JSONPath / JS / 模板规则，不需要 @text 等 action。"""
    v = value.strip()
    return (v.startswith("$.") or v.startswith("@json:") or v.startswith("<js>")
            or v.startswith("@js:") or "{{" in v)


# 裸 action 词：Default 模式下对当前元素取文本/属性，Legado 原生支持
# （AnalyzeByJSoup.getResultLast 的 when 分支：text/textNodes/ownText/html/all + 属性名）
BARE_ACTIONS = {"text", "textNodes", "ownText", "html", "all",
                "href", "src", "value", "content", "outerHtml"}


def _has_action(value: str) -> bool:
    """字段是否带有效 action（@text/@href 或裸 action 词）。"""
    v = value.strip()
    if "@" in v or _is_json_or_js_rule(v):
        return True
    last = v.split()[-1] if v else ""
    return last in BARE_ACTIONS


def _collect_js_snippets(value):
    """提取字段里的可执行 JS 片段。"""
    if not isinstance(value, str):
        return []
    snippets = []
    m = re.search(r"<js>\s*([\s\S]*?)\s*</js>", value, re.I)
    if m:
        snippets.append(m.group(1))
    idx = value.find("@js:")
    if idx != -1:
        snippets.append(value[idx + 4:])
    return snippets


def _node_check_js(code: str):
    """用 node --check 校验 JS 语法。返回错误信息或 None。"""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(code)
            path = f.name
        proc = subprocess.run(["node", "--check", path], capture_output=True,
                              text=True, timeout=15)
        Path(path).unlink(missing_ok=True)
        if proc.returncode != 0:
            msg = (proc.stderr or "").strip().splitlines()
            return msg[0] if msg else "JS 语法错误"
        return None
    except FileNotFoundError:
        return None  # 没有 node 就跳过，不误报
    except Exception:
        return None


# ── 内置检查（不依赖 rule pack） ────────────────────────────────────────────

def check_structure(source) -> list:
    """顶层数组、必填字段、占位符。"""
    issues = []
    for name in REQUIRED_TOP:
        if name not in source:
            issues.append({
                "severity": "error", "type": "missing_field",
                "field": name, "message": f"缺少必填顶层字段: {name}",
            })
        elif isinstance(source.get(name), str) and not source[name].strip():
            issues.append({
                "severity": "error", "type": "missing_field",
                "field": name, "message": f"必填顶层字段为空: {name}",
            })
    if _is_blank(source.get("searchUrl")):
        issues.append({
            "severity": "error", "type": "missing_field",
            "field": "searchUrl", "message": "searchUrl 不能为空（搜索是必需入口）",
        })
    for group, fields in REQUIRED_NESTED.items():
        g = source.get(group)
        if not isinstance(g, dict):
            issues.append({
                "severity": "error", "type": "missing_field",
                "field": group, "message": f"{group} 缺失或不是对象",
            })
            continue
        for f in fields:
            if _is_blank(g.get(f)):
                issues.append({
                    "severity": "error", "type": "missing_field",
                    "field": f"{group}.{f}", "message": f"缺少必填字段: {group}.{f}",
                })

    # 占位符检测
    for group in RULE_GROUPS:
        g = source.get(group)
        if not isinstance(g, dict):
            continue
        for fname, fval in g.items():
            if isinstance(fval, str) and fval.strip() in PLACEHOLDER_TEXT:
                issues.append({
                    "severity": "error", "type": "placeholder",
                    "field": f"{group}.{fname}",
                    "message": f"{group}.{fname} 仍是模板占位符「{fval.strip()}」，未替换为真实规则",
                })
    if isinstance(source.get("searchUrl"), str) and source["searchUrl"].strip() in PLACEHOLDER_TEXT:
        issues.append({
            "severity": "error", "type": "placeholder", "field": "searchUrl",
            "message": "searchUrl 仍是模板占位符",
        })
    return issues


def check_embedded_js(source) -> list:
    """内嵌 JS 语法检查（node --check）。"""
    issues = []
    for group in RULE_GROUPS:
        g = source.get(group)
        if not isinstance(g, dict):
            continue
        for fname, fval in g.items():
            for snippet in _collect_js_snippets(fval):
                err = _node_check_js(snippet)
                if err:
                    issues.append({
                        "severity": "error", "type": "js_syntax",
                        "field": f"{group}.{fname}",
                        "message": f"{group}.{fname} 内嵌 JS 语法错误: {err}",
                    })
                    break
    return issues


def check_risky_fields(source) -> list:
    """真正的高风险字段提示（warning，不阻断）。

    只标记会改变执行路径的复杂逻辑：JS、WebView、java.*。
    普通 ## 正则净化/提取是日常写法，不算风险。
    """
    warnings = []
    for group in RULE_GROUPS:
        g = source.get(group)
        if not isinstance(g, dict):
            continue
        for fname, fval in g.items():
            if not isinstance(fval, str) or not fval.strip():
                continue
            if ("<js>" in fval or fval.startswith("@js:") or "webView" in fval
                    or "java." in fval or fval.startswith("@")):
                warnings.append({
                    "severity": "warning", "type": "risky_rule",
                    "field": f"{group}.{fname}",
                    "message": f"{group}.{fname} 含 JS/WebView/java.* 逻辑，需实测确认",
                })
    return warnings


# ── rule pack 检查 ─────────────────────────────────────────────────────────

def _load_rule_pack() -> dict:
    with open(RULE_PACK_PATH, encoding="utf-8") as f:
        return json.load(f)


def _check_forbid_field(source, rule):
    group, _, field = rule["target"].partition(".")
    g = source.get(group)
    if isinstance(g, dict) and field in g:
        return [{"severity": rule["severity"], "type": "forbid_field",
                 "field": rule["target"], "ruleId": rule["id"],
                 "message": rule["message"]}]
    return []


def _check_forbid_search_url_token(source, rule):
    url = source.get("searchUrl") or ""
    for token in rule.get("tokens", []):
        if token in url:
            return [{"severity": rule["severity"], "type": "forbid_token",
                     "field": "searchUrl", "ruleId": rule["id"],
                     "message": f"{rule['message']} 检测到: {token}"}]
    return []


def _check_forbid_selector_tokens(source, rule):
    text = json.dumps(source, ensure_ascii=False)
    for token in rule.get("tokens", []):
        if token in text:
            return [{"severity": rule["severity"], "type": "forbid_token",
                     "field": "*", "ruleId": rule["id"],
                     "message": f"{rule['message']} 检测到: {token}"}]
    return []


def _check_text_fields_need_action(source, rule):
    """文本字段 action 检查。

    实证（真引擎）：Default 模式下裸选择器（如 "a"、"h1"）默认取元素文本，
    是合法写法；裸 action 词（text/href）作用于当前元素，同样合法。
    只有形如纯属性名（如单独一个 "src"）且前面没有选择器时才可疑——降为 warning。
    """
    issues = []
    for group in ["ruleSearch", "ruleBookInfo", "ruleToc"]:
        g = source.get(group)
        if not isinstance(g, dict):
            continue
        for f in rule.get("fields", []):
            v = g.get(f)
            if not isinstance(v, str) or not v.strip():
                continue
            if _has_action(v) or " " in v.strip() or v.startswith(".") \
                    or v.startswith("#") or v.startswith("["):
                continue
            if v.strip() in BARE_ACTIONS:
                # 单独一个属性/action 词，前面没有选择器——多半是漏写选择器
                issues.append({
                    "severity": "warning", "type": "suspicious_rule",
                    "field": f"{group}.{f}", "ruleId": rule["id"],
                    "message": f'{group}.{f}: "{v}" 是裸 action 词，没有选择器；'
                               f"如果本意是取当前元素文本，请确认上下文正确",
                })
    return issues


def _check_url_fields_need_href(source, rule):
    issues = []
    for group in ["ruleSearch", "ruleToc", "ruleBookInfo"]:
        g = source.get(group)
        if not isinstance(g, dict):
            continue
        for f in rule.get("fields", []):
            v = g.get(f)
            if not isinstance(v, str) or not v.strip():
                continue
            if ("@href" in v or "@js" in v or _has_action(v)
                    or v.startswith("http") or v.startswith("/") or v.startswith("##")):
                continue
            issues.append({
                "severity": rule["severity"], "type": "missing_href",
                "field": f"{group}.{f}", "ruleId": rule["id"],
                "message": f'{group}.{f}: "{v}" — {rule["message"]}',
            })
            break
    return issues


def _check_cookie_login_shape(source, rule):
    """登录态书源结构检查。

    明确登录证据（loginUrl / Authorization header）→ 缺配套结构报 error；
    仅 enabledCookieJar（可能只是持久化 session token，如反爬预热 cookie）→ warning。
    """
    has_login_url = bool(source.get("loginUrl"))
    has_auth = "Authorization" in str(source.get("header", ""))
    has_cookie_jar = source.get("enabledCookieJar") is True

    if not (has_login_url or has_auth or has_cookie_jar):
        return []

    issues = []
    if has_login_url or has_auth:
        # 明确需要登录：检查登录三件套
        if not has_cookie_jar:
            issues.append({
                "severity": rule["severity"], "type": "login_shape",
                "field": "enabledCookieJar", "ruleId": rule["id"],
                "message": "需要登录态的书源必须设置 enabledCookieJar: true",
            })
        if not has_login_url:
            issues.append({
                "severity": rule["severity"], "type": "login_shape",
                "field": "loginUrl", "ruleId": rule["id"],
                "message": "需要登录态的书源必须提供 loginUrl",
            })
        if "java.getCookie" not in str(source.get("header", "")):
            issues.append({
                "severity": rule["severity"], "type": "login_shape",
                "field": "header", "ruleId": rule["id"],
                "message": "header 必须使用 java.getCookie 动态注入 Cookie，不能写死",
            })
    elif has_cookie_jar:
        # 仅 CookieJar：可能只是持久化 session token，提示确认
        issues.append({
            "severity": "warning", "type": "login_shape",
            "field": "enabledCookieJar", "ruleId": rule["id"],
            "message": "enabledCookieJar: true 但无 loginUrl——如果站点需要登录，"
                       "请补 loginUrl 与 java.getCookie header；如果只是持久化反爬 "
                       "session cookie，可忽略此提示",
        })
    return issues


def _check_webjs_should_return(source, rule):
    webjs = (source.get("ruleContent") or {}).get("webJs")
    if not webjs:
        return []
    if re.search(r"return|while\s*\(|sleep|document\.querySelector|querySelector", str(webjs)):
        return []
    return [{"severity": rule["severity"], "type": "webjs_return",
             "field": "ruleContent.webJs", "ruleId": rule["id"],
             "message": rule["message"]}]


def check_explore_layout(source) -> list:
    """发现页布局质量检查（参考 references/explore-layout.md）。

    静态启发式：扫描 exploreUrl 里的 JS/JSON 文本，检查是否使用了
    会导致"不整齐"的写法。仅产生 warning（不阻断），但会在报告中列出。
    """
    explore = source.get("exploreUrl")
    if not explore or not isinstance(explore, str):
        return []
    warnings = []
    text = explore

    # 1. 无效字段（Legado 不支持，写了无效果）
    for token in ("textAlign", "fontWeight", "textSize", "fontColor"):
        if token in text:
            warnings.append({
                "severity": "warning", "type": "explore_layout",
                "field": "exploreUrl",
                "message": f"exploreUrl 使用了无效样式字段「{token}」——"
                           f"Legado 只支持 layout_* 系列字段，该字段会被静默忽略（白写）。"
                           f"详见 references/explore-layout.md",
            })

    # 2. 两列百分比 0.5 会溢出（3 列 0.33 / 4 列 0.25 同理）
    overflow_pcts = []
    if re.search(r"layout_flexBasisPercent\s*[\"']?\s*[:=]\s*0?\.5\b", text):
        overflow_pcts.append("0.5（两列会溢出，应用 0.45）")
    if re.search(r"layout_flexBasisPercent\s*[\"']?\s*[:=]\s*0?\.33\b", text):
        overflow_pcts.append("0.33（三列会溢出，应用 0.29）")
    if re.search(r"layout_flexBasisPercent\s*[\"']?\s*[:=]\s*0?\.25\b", text):
        overflow_pcts.append("0.25（四列会溢出，应用 0.2）")
    if overflow_pcts:
        warnings.append({
            "severity": "warning", "type": "explore_layout",
            "field": "exploreUrl",
            "message": "exploreUrl 使用了会溢出的百分比：" + "；".join(overflow_pcts)
                       + "。溢出会导致假换行、列不齐。详见 references/explore-layout.md",
        })

    # 3. 完全没有 style/flexBasisPercent → 散排 chips（不整齐的根源）
    if ("layout_flexBasisPercent" not in text
            and "flexBasisPercent" not in text
            and ("push(" in text or "[" in text)):
        warnings.append({
            "severity": "warning", "type": "explore_layout",
            "field": "exploreUrl",
            "message": "exploreUrl 没有使用 layout_flexBasisPercent——按钮宽度会随文字变化，"
                       "呈现大小不一的散排 chips（发现页不整齐的根源）。"
                       "请套用 references/explore-layout.md 的黄金模板",
        })

    # 4. 分组标题（url 为空）缺 flexBasisPercent: 1.0
    # 启发式：找 title+url:"" 的组合，检查其后 250 字符内是否有 1.0 / 1。
    # 排除两类合法写法：
    #   a) 等宽格子空位补齐：同时带 layout_wrapBefore / layout_flexGrow（网格布局特征）
    #   b) 标题为空格的占位符（'　' / ' ' 开头）
    for m in re.finditer(r"title\s*:\s*[\"']([^\"']*)[\"'][^}]{0,200}?url\s*:\s*[\"']{2}", text):
        title_text = m.group(1)
        window = text[m.start():m.start() + 300]
        # 跳过空位补齐（全角/半角空格标题）
        if title_text.strip() == "" or title_text.strip("　 ") == "":
            continue
        # 跳过网格布局（带 wrapBefore 或 flexGrow 的条目）
        if ("layout_wrapBefore" in window or "layout_flexGrow" in window):
            continue
        if ("flexBasisPercent" in window
                and not re.search(r"flexBasisPercent\s*[\"']?\s*[:=]\s*1(?:\.0)?\b", window)):
            warnings.append({
                "severity": "warning", "type": "explore_layout",
                "field": "exploreUrl",
                "message": "分组标题（url 为空字符串）的 flexBasisPercent 不是 1.0——"
                           "标题只占一格宽度、与按钮混排。分组标题应设 "
                           "{layout_flexBasisPercent: 1.0, layout_justifySelf: \"center\"}。"
                           "详见 references/explore-layout.md",
            })
            break

    return warnings


_CHECKERS = {
    "forbidField": _check_forbid_field,
    "forbidSearchUrlToken": _check_forbid_search_url_token,
    "forbidSelectorTokens": _check_forbid_selector_tokens,
    "textFieldsNeedAction": _check_text_fields_need_action,
    "urlFieldsNeedHref": _check_url_fields_need_href,
    "cookieLoginShape": _check_cookie_login_shape,
    "webJsShouldReturn": _check_webjs_should_return,
}


def run_rule_pack_checks(source, pack) -> tuple:
    issues = []
    checked = []
    for rule in pack.get("rules", []):
        checker = _CHECKERS.get(rule.get("checkKind"))
        if not checker:
            continue
        checked.append(rule["id"])
        issues.extend(checker(source, rule))
    return issues, checked


# ── 主流程 ─────────────────────────────────────────────────────────────────

def audit(source, source_hash: str = "") -> dict:
    pack = _load_rule_pack()
    issues = []
    issues += check_structure(source)
    issues += check_embedded_js(source)
    pack_issues, checked = run_rule_pack_checks(source, pack)
    issues += pack_issues
    issues += check_explore_layout(source)
    warnings = check_risky_fields(source)

    errors = [i for i in issues if i.get("severity") == "error"]
    warn_only = [i for i in issues if i.get("severity") != "error"]
    return {
        "_generatedBy": "rule_audit.py",
        "_schemaVersion": "1.0",
        "sourceHash": source_hash,
        "status": "failed" if errors else "passed",
        "errors": errors,
        "warnings": warn_only + warnings,
        "checkedRuleIds": checked,
    }


def _print_human(report: dict, path: str):
    print("=" * 60)
    print(" 书源静态规则审计")
    print("=" * 60)
    print(f"文件: {path}")
    print(f"状态: {'通过' if report['status'] == 'passed' else '失败'}")
    print()
    if report["errors"]:
        print(f"错误 ({len(report['errors'])}):")
        for i in report["errors"]:
            print(f"  ✗ [{i.get('type', '?')}] {i['message']}")
        print()
    if report["warnings"]:
        print(f"警告 ({len(report['warnings'])}):")
        for w in report["warnings"]:
            print(f"  ! [{w.get('type', '?')}] {w['message']}")
        print()
    if report["status"] == "passed":
        print("静态审计通过。注意：这只代表没有已知静态错误，")
        print("不代表书源可用——请继续运行 verify_source.py 做真引擎验证。")


def main():
    parser = argparse.ArgumentParser(description="书源静态规则审计")
    parser.add_argument("source", help="书源 JSON 文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args()

    path = Path(args.source)
    if not path.exists():
        print(f"文件不存在: {path}", file=sys.stderr)
        return 2

    raw = path.read_text(encoding="utf-8")
    import hashlib
    source_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        report = {
            "_generatedBy": "rule_audit.py", "_schemaVersion": "1.0",
            "sourceHash": source_hash, "status": "failed",
            "errors": [{"severity": "error", "type": "json_syntax",
                        "message": f"JSON 解析失败: {e}"}],
            "warnings": [], "checkedRuleIds": [],
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"JSON 解析失败: {e}")
        return 1

    if not isinstance(data, list):
        report = {
            "_generatedBy": "rule_audit.py", "_schemaVersion": "1.0",
            "sourceHash": source_hash, "status": "failed",
            "errors": [{"severity": "error", "type": "top_level",
                        "message": "顶层必须是 JSON 数组 [ {...} ]，"
                                   "单个对象会导致 Legado 导入报 "
                                   "Expected BEGIN_ARRAY but was BEGIN_OBJECT"}],
            "warnings": [], "checkedRuleIds": [],
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(report["errors"][0]["message"])
        return 1

    # 逐源审计，聚合
    all_errors, all_warnings, checked = [], [], []
    for src in data:
        if not isinstance(src, dict):
            all_errors.append({"severity": "error", "type": "structure",
                               "message": "数组元素不是对象"})
            continue
        r = audit(src, source_hash)
        all_errors += r["errors"]
        all_warnings += r["warnings"]
        checked += r["checkedRuleIds"]

    report = {
        "_generatedBy": "rule_audit.py", "_schemaVersion": "1.0",
        "sourceHash": source_hash,
        "status": "failed" if all_errors else "passed",
        "sourceCount": len(data),
        "errors": all_errors,
        "warnings": all_warnings,
        "checkedRuleIds": sorted(set(checked)),
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report, str(path))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())

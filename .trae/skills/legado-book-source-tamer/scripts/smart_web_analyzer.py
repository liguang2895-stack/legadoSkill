"""
智能网站分析器（ZCode 版）
自动分析网站结构，识别搜索表单、分页、列表结构、AJAX 线索、防护特征。
从 legadoSkill 原版移植，去除 Trae/Coze 运行时依赖，改为独立 CLI。
"""

import re
import json
from typing import Dict
from urllib.parse import urljoin as _urljoin
from bs4 import BeautifulSoup
import requests


def urljoin(base: str, url: str) -> str:
    """简单的URL拼接"""
    return _urljoin(base, url)


def _analyze_search_form(soup: BeautifulSoup, base_url: str) -> Dict:
    """分析搜索表单：method / action / 参数名"""
    result = {"has_form": False}
    form = soup.find("form")
    if not form:
        return result
    result["has_form"] = True
    result["method"] = (form.get("method") or "GET").upper()
    action = form.get("action") or ""
    result["action"] = urljoin(base_url, action) if action else base_url
    inputs = []
    for inp in form.find_all(["input", "select", "textarea"]):
        name = inp.get("name")
        if name:
            itype = inp.get("type", inp.name)
            inputs.append({"name": name, "type": itype})
    result["fields"] = inputs
    # 猜测关键词字段
    kw = [f["name"] for f in inputs if any(k in f["name"].lower() for k in
          ("key", "keyword", "search", "q", "word", "name", "s"))]
    result["likely_keyword_fields"] = kw
    return result


def _analyze_pagination(soup: BeautifulSoup, base_url: str) -> Dict:
    """分析分页结构"""
    info = {"links": [], "has_select": False}
    for a in soup.find_all("a", string=True):
        text = a.get_text(strip=True)
        if text and any(k in text for k in ("下一页", "下页", "下一章", "下章", "next", "›", "»")):
            href = a.get("href", "")
            info["links"].append({"text": text, "href": urljoin(base_url, href) if href else ""})
        if len(info["links"]) >= 5:
            break
    select = soup.find("select", onchange=True) or soup.find("select")
    if select and select.find("option", value=True):
        info["has_select"] = True
        info["select_options"] = [o.get("value") for o in select.find_all("option", value=True)[:5]]
    return info


def _analyze_list_structure(soup: BeautifulSoup) -> Dict:
    """识别重复元素结构，推荐候选列表选择器"""
    from collections import Counter
    parent_counter = Counter()
    for tag in soup.find_all(["li", "tr", "div", "a"]):
        parent = tag.parent
        if parent and parent.name:
            parent_counter[(parent.name, parent.get("class") and " ".join(parent.get("class")) or "")] += 1
    candidates = [
        {"parent": f"{n}.{c}" if c else n, "children_count": cnt}
        for (n, c), cnt in parent_counter.most_common(10) if cnt >= 5
    ]
    return {"repeated_structures": candidates}


def _analyze_ajax(soup: BeautifulSoup) -> Dict:
    """收集 AJAX 线索：外部 JS 与常见接口关键字"""
    js_files = [s.get("src") for s in soup.find_all("script", src=True)]
    return {"external_js": js_files[:20], "js_count": len(js_files)}


def _analyze_security(soup: BeautifulSoup, html: str) -> Dict:
    """防护特征检测"""
    text = soup.get_text()[:2000]
    cf = any(m in html[:8000] for m in ("Just a moment", "Checking your browser", "DDoS protection", "cf-browser-verification"))
    return {
        "cloudflare_suspect": cf,
        "title": soup.title.get_text(strip=True) if soup.title else "",
        "meta_refresh": bool(soup.find("meta", attrs={"http-equiv": "refresh"})),
    }


def smart_analyze_website(url: str, timeout: int = 30) -> str:
    """智能分析网站结构，输出报告"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=timeout, verify=False)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    from smart_fetch import SmartRequest
    charset = SmartRequest()._detect_encoding(response)

    analysis = {
        "url": url,
        "charset": charset,
        "search_info": _analyze_search_form(soup, url),
        "pagination_info": _analyze_pagination(soup, url),
        "list_structure": _analyze_list_structure(soup),
        "ajax_info": _analyze_ajax(soup),
        "security_info": _analyze_security(soup, html),
    }
    return json.dumps(analysis, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import argparse, sys, io, warnings, urllib3
    warnings.filterwarnings("ignore")
    urllib3.disable_warnings()
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="智能分析网站结构（搜索表单/分页/列表/AJAX/防护）")
    p.add_argument("url", help="网站 URL")
    p.add_argument("--timeout", type=int, default=30)
    args = p.parse_args()
    try:
        print(smart_analyze_website(args.url, args.timeout))
    except Exception as e:
        print(f"[分析失败] {e}")
        print("提示: 网站可能已失效、被墙或有 TLS/验证防护。可换备用域名，或改用")
        print("      smart_fetch.py 抓取（自动重试+编码处理）后人工分析 HTML。")
        sys.exit(1)

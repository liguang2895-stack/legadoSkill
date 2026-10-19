#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Legado 真实书源案例库检索（kb_query.py）

在 legadoSkill 仓库的 assets/ 知识库中做全文关键词检索，返回命中的案例文件。
知识库包含 170+ 真实书源分析（晋江/番茄/笔趣阁/漫画/聚合源/有声等）与规则教程。

知识库根目录自动发现顺序:
    1. 环境变量 LEGADO_KB_ROOT（指向 legadoSkill 仓库目录或其 assets/）
    2. 技能目录旁的 legadoSkill/ 仓库
    3. 当前工作区的 legadoSkill/

用法:
    python kb_query.py "漫画 懒加载"          # 多关键词 AND 检索
    python kb_query.py --list                 # 列出全部案例
    python kb_query.py --show <文件名>        # 展示某案例全文
    python kb_query.py --root <路径> "关键词" # 手动指定知识库根
"""

import os
import sys
import io
import re
import argparse

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SKILL_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_HINT = "git clone https://github.com/liguang2895-stack/legadoSkill.git"


def _candidate_roots():
    roots = []
    env = os.environ.get("LEGADO_KB_ROOT")
    if env:
        roots.append(env)
    # 从脚本目录逐级向上找：既支持技能与 legadoSkill 仓库同级，
    # 也支持技能本身就装在 legadoSkill 仓库内（如 .trae/skills/legado-book-source-tamer/）。
    here = SKILL_SCRIPT_DIR
    for _ in range(6):
        here = os.path.dirname(here)
        if here in ("/", "") or here.endswith(os.sep) and len(here) <= 3:
            break
        roots.append(here)
        roots.append(os.path.join(here, "legadoSkill"))
    # 当前工作区
    roots.append(os.path.join(os.getcwd(), "legadoSkill"))
    return roots


def discover_kb_root(explicit=None):
    """返回 assets 知识库根目录（含 legado_knowledge_base.md 的目录），找不到返回 None"""
    candidates = []
    if explicit:
        candidates.append(explicit)
    candidates += _candidate_roots()
    for c in candidates:
        if not c or not os.path.isdir(c):
            continue
        # 允许直接传到 assets/ 或仓库根
        if os.path.isfile(os.path.join(c, "legado_knowledge_base.md")):
            return c
        inner = os.path.join(c, "assets")
        if os.path.isfile(os.path.join(inner, "legado_knowledge_base.md")):
            return inner
    return None


def list_cases(root):
    cases = []
    kb_sources = os.path.join(root, "knowledge_base", "book_sources")
    if os.path.isdir(kb_sources):
        for f in sorted(os.listdir(kb_sources)):
            if f.endswith(".md"):
                cases.append(("案例", os.path.join(kb_sources, f), f))
    for f in sorted(os.listdir(root)):
        if f.endswith((".md", ".txt")) and os.path.isfile(os.path.join(root, f)):
            cases.append(("教程/资料", os.path.join(root, f), f))
    return cases


def search(cases, keywords):
    hits = []
    for kind, path, name in cases:
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        score = sum(text.count(k) for k in keywords)
        name_score = sum(name.count(k) for k in keywords) * 10
        if score + name_score > 0:
            hits.append((score + name_score, kind, path, name))
    hits.sort(reverse=True)
    return hits


def main():
    p = argparse.ArgumentParser(description="Legado 真实书源案例库检索")
    p.add_argument("keywords", nargs="*", help="检索关键词（多个为 AND）")
    p.add_argument("--list", action="store_true", help="列出全部文件")
    p.add_argument("--show", metavar="FILE", help="展示指定文件全文（名字模糊匹配）")
    p.add_argument("--root", metavar="PATH", help="手动指定知识库根（legadoSkill 仓库或 assets/）")
    p.add_argument("--top", type=int, default=10, help="返回命中条数（默认10）")
    args = p.parse_args()

    root = discover_kb_root(args.root)
    if not root:
        print("[未找到知识库]")
        print(f"请先克隆案例库仓库，或用 --root 指定路径:\n  {REPO_HINT}")
        sys.exit(2)
    print(f"[知识库] {root}\n")

    cases = list_cases(root)

    if args.list:
        for kind, path, name in cases:
            print(f"[{kind}] {name}")
        print(f"\n共 {len(cases)} 个文件")
        return

    if args.show:
        matches = [c for c in cases if args.show in c[2]]
        if not matches:
            print(f"没有匹配 '{args.show}' 的文件")
            sys.exit(1)
        path = matches[0][1] if len(matches) == 1 else max(matches, key=lambda c: len(c[2]))[1]
        print(f"===== {path} =====")
        print(open(path, encoding="utf-8", errors="ignore").read())
        return

    if not args.keywords:
        p.error("需要检索关键词，或使用 --list / --show")

    # 允许 "漫画 懒加载" 整体传入：按空白再拆分为多关键词
    keywords = [w for arg in args.keywords for w in arg.split() if w]
    hits = search(cases, keywords)
    if not hits:
        print("没有命中。尝试更换关键词（如：漫画/懒加载/POST/聚合/有声/nextContentUrl/授权）。")
        return
    for score, kind, path, name in hits[: args.top]:
        print(f"[{score:>4}] [{kind}] {name}")
    print("\n用 --show <文件名> 查看全文。")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
书源产物整理 CLI（封装 debugger/engine/file_organizer.py）

把书源 JSON、抓取的 HTML、调试脚本等归档到 temp/<书源名>/。

用法:
    python organize_files.py --name 笔趣阁 --files 笔趣阁.json search.html
    python organize_files.py --name 笔趣阁 --files a.json --copy   # 复制而非移动
"""

import sys
import os
import io
import argparse

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from debugger.engine.file_organizer import BookSourceFileOrganizer  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="整理书源相关文件到 temp/<书源名>/")
    p.add_argument("--name", required=True, help="书源名称（作为子文件夹名）")
    p.add_argument("--files", nargs="*", default=[], help="要归档的文件列表")
    p.add_argument("--copy", action="store_true", help="复制模式（默认移动）")
    p.add_argument("--root", default=os.getcwd(),
                   help="项目根目录（默认当前工作目录，temp/ 建在其下）")
    args = p.parse_args()

    organizer = BookSourceFileOrganizer(args.root)
    result = organizer.organize_files(
        book_source_name=args.name,
        files_to_move=[os.path.abspath(f) for f in args.files],
        copy_mode=args.copy,
    )
    print(("OK " if result.success else "WARN ") + result.message)
    if result.subfolder_path:
        print(f"文件夹: {result.subfolder_path}")
    for f in result.moved_files:
        print(f"  + {f}")
    for e in result.errors:
        print(f"  ! {e}")
    sys.exit(0 if result.success else 2)


if __name__ == "__main__":
    main()

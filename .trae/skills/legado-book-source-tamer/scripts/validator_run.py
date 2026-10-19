#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
validator_run.py — 内嵌 Legado 验证器生命周期管理

功能：
  setup-jre  检测 Java 21+；缺失时从 Adoptium 官方 API 下载便携 JRE 到 tools/jre/
  start      选空闲端口启动 validator jar，探活后写 validator/.runtime.json
  stop       按 pid 停止 validator
  status     查看运行状态

用法（在 SKILL_DIR/scripts 下执行）：
    python validator_run.py setup-jre
    python validator_run.py start
    python validator_run.py status
    python validator_run.py stop
"""

import argparse
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SKILL_DIR = Path(__file__).resolve().parent.parent
VALIDATOR_DIR = SKILL_DIR / "validator"
JAR_PATH = VALIDATOR_DIR / "app" / "legado-source-validator.jar"
RUNTIME_FILE = VALIDATOR_DIR / ".runtime.json"
LOG_DIR = VALIDATOR_DIR / "logs"
TOOLS_DIR = SKILL_DIR / "tools"
PORTABLE_JRE_DIR = TOOLS_DIR / "jre"

# Adoptium 官方 API：最新 JRE 21 Windows x64
ADOPTIUM_JRE21_URL = (
    "https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jre/hotspot/normal/eclipse"
)
JAVA_MAJOR_REQUIRED = 21


# ── Java 探测 ──────────────────────────────────────────────────────────────

def _java_major(java_exe: str) -> int:
    """返回 java 可执行文件的主版本号；失败返回 0。"""
    try:
        out = subprocess.run(
            [java_exe, "-version"], capture_output=True, text=True, timeout=15
        )
        text = (out.stderr or "") + (out.stdout or "")
        for token in text.replace('"', " ").split():
            token = token.strip()
            if token and token[0].isdigit() and "." in token:
                major = token.split(".")[0]
                if major.isdigit():
                    return int(major)
    except Exception:
        pass
    return 0


def find_java() -> tuple:
    """按优先级查找可用 Java。返回 (java_exe, source_desc) 或 (None, None)。"""
    candidates = []
    if sys.platform == "win32":
        candidates.append((PORTABLE_JRE_DIR / "bin" / "java.exe", "便携 JRE (tools/jre)"))
    else:
        candidates.append((PORTABLE_JRE_DIR / "bin" / "java", "便携 JRE (tools/jre)"))
    env_home = os.environ.get("JAVA_HOME", "").strip()
    if env_home:
        exe = Path(env_home) / "bin" / ("java.exe" if sys.platform == "win32" else "java")
        candidates.append((exe, "JAVA_HOME"))
    which = shutil.which("java")
    if which:
        candidates.append((Path(which), "系统 PATH"))

    for exe, desc in candidates:
        if exe and Path(exe).exists():
            major = _java_major(str(exe))
            if major >= JAVA_MAJOR_REQUIRED:
                return str(exe), desc
    return None, None


def _download_file(url: str, dest: Path) -> str:
    """带浏览器 UA 下载（GitHub 重定向会拒绝默认 UA）。返回错误信息或空串。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f, length=1024 * 1024)
        return ""
    except Exception as e:
        return f"下载失败: {e}"


def download_portable_jre() -> tuple:
    """下载并解压便携 JRE 21 到 tools/jre/。返回 (java_exe, error)。"""
    PORTABLE_JRE_DIR.parent.mkdir(parents=True, exist_ok=True)
    zip_path = TOOLS_DIR / "jre21-download.zip"
    print(f"[setup-jre] 下载 JRE 21（约 50MB）: {ADOPTIUM_JRE21_URL}")
    err = _download_file(ADOPTIUM_JRE21_URL, zip_path)
    if err:
        return None, err
    try:
        print(f"[setup-jre] 解压到 {PORTABLE_JRE_DIR} ...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(TOOLS_DIR)
        # Adoptium 压缩包解压后顶层目录形如 jdk-21.x.x+x-jre
        extracted = [d for d in TOOLS_DIR.iterdir() if d.is_dir() and d.name.startswith("jdk-")]
        if not extracted:
            return None, "解压后未找到 JRE 目录"
        src = extracted[0]
        if PORTABLE_JRE_DIR.exists():
            shutil.rmtree(PORTABLE_JRE_DIR)
        src.rename(PORTABLE_JRE_DIR)
    except Exception as e:
        return None, f"解压失败: {e}"
    finally:
        try:
            zip_path.unlink()
        except OSError:
            pass

    exe = PORTABLE_JRE_DIR / "bin" / ("java.exe" if sys.platform == "win32" else "java")
    if exe.exists():
        return str(exe), None
    return None, "解压后未找到 bin/java"


def cmd_setup_jre(_args) -> int:
    java, source = find_java()
    if java:
        major = _java_major(java)
        print(json.dumps({
            "ok": True, "java": java, "major": major, "source": source,
            "message": f"已找到可用 Java {major}（{source}）",
        }, ensure_ascii=False, indent=2))
        return 0

    print("[setup-jre] 未找到 Java 21+，尝试自动下载便携 JRE ...")
    java, err = download_portable_jre()
    if java:
        major = _java_major(java)
        print(json.dumps({
            "ok": True, "java": java, "major": major, "source": "便携 JRE (tools/jre)",
            "message": f"便携 JRE 安装完成（Java {major}）",
        }, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps({
        "ok": False,
        "error": err,
        "message": "自动下载失败。请手动安装 Java 21 后重试，或手动下载 JRE 解压到 tools/jre/。",
        "manualOptions": [
            "winget install EclipseAdoptium.Temurin.21.JRE",
            f"或浏览器打开 {ADOPTIUM_JRE21_URL} 下载 zip，解压后把含 bin/java.exe 的目录改名为 jre 放到 {TOOLS_DIR}",
        ],
    }, ensure_ascii=False, indent=2))
    return 1


# ── 端口与运行时状态 ───────────────────────────────────────────────────────

def _reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _read_runtime() -> dict:
    try:
        data = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
        if data.get("url") and isinstance(data.get("port"), int):
            return data
    except Exception:
        pass
    return {}


def _write_runtime(data: dict):
    RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _remove_runtime():
    try:
        RUNTIME_FILE.unlink()
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    """判断进程是否存活。

    Windows 上 os.kill(pid, 0) 语义不可靠（可能直接 TerminateProcess 或抛错），
    改用 tasklist 查询；POSIX 用 signal 0。
    """
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=10)
            return str(pid) in (out.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def _probe(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/sources", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def cmd_start(_args) -> int:
    if not JAR_PATH.exists():
        print(json.dumps({
            "ok": False, "error": f"validator jar 不存在: {JAR_PATH}",
        }, ensure_ascii=False, indent=2))
        return 1

    # 已在运行则直接复用
    runtime = _read_runtime()
    if runtime and _probe(runtime["url"]):
        print(json.dumps({
            "ok": True, "running": True, "url": runtime["url"], "pid": runtime.get("pid"),
            "message": "validator 已在运行",
        }, ensure_ascii=False, indent=2))
        return 0

    java, source = find_java()
    if not java:
        print(json.dumps({
            "ok": False,
            "error": "未找到 Java 21+。先运行: python validator_run.py setup-jre",
        }, ensure_ascii=False, indent=2))
        return 1

    port = _reserve_port()
    url = f"http://127.0.0.1:{port}"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"validator-{int(time.time())}.log"

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

    with open(log_path, "wb") as log_fd:
        proc = subprocess.Popen(
            [java, "-jar", str(JAR_PATH), "--port", str(port)],
            stdout=log_fd, stderr=log_fd, stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            cwd=str(VALIDATOR_DIR),
        )

    # 探活：最多 20s
    deadline = time.time() + 20
    while time.time() < deadline:
        if _probe(url):
            _write_runtime({
                "pid": proc.pid, "port": port, "url": url,
                "logPath": str(log_path), "java": java,
                "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            print(json.dumps({
                "ok": True, "running": True, "url": url, "pid": proc.pid,
                "logPath": str(log_path), "javaSource": source,
                "message": "validator 启动成功",
            }, ensure_ascii=False, indent=2))
            return 0
        if proc.poll() is not None:
            tail = ""
            try:
                tail = log_path.read_text(encoding="utf-8", errors="replace")[-800:]
            except Exception:
                pass
            print(json.dumps({
                "ok": False, "error": f"validator 进程退出（code={proc.returncode}）",
                "logTail": tail,
            }, ensure_ascii=False, indent=2))
            return 1
        time.sleep(0.25)

    print(json.dumps({
        "ok": False, "error": "validator 启动超时（20s）", "logPath": str(log_path),
    }, ensure_ascii=False, indent=2))
    return 1


def cmd_stop(_args) -> int:
    runtime = _read_runtime()
    if not runtime:
        print(json.dumps({"ok": True, "running": False, "message": "没有记录的运行实例"},
                         ensure_ascii=False, indent=2))
        return 0
    pid = runtime.get("pid")
    if pid and _pid_alive(pid):
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=15)
            else:
                os.kill(pid, 15)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"停止失败: {e}"},
                             ensure_ascii=False, indent=2))
            return 1
    _remove_runtime()
    print(json.dumps({"ok": True, "running": False, "message": "validator 已停止"},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_status(_args) -> int:
    runtime = _read_runtime()
    if runtime and _probe(runtime["url"]):
        print(json.dumps({
            "ok": True, "running": True, "url": runtime["url"], "pid": runtime.get("pid"),
        }, ensure_ascii=False, indent=2))
        return 0
    if runtime:
        _remove_runtime()
    print(json.dumps({"ok": True, "running": False}, ensure_ascii=False, indent=2))
    return 0


def ensure_running() -> tuple:
    """供其他脚本调用：确保 validator 运行，返回 (url, error)。"""
    runtime = _read_runtime()
    if runtime and _probe(runtime["url"]):
        return runtime["url"], None
    rc = cmd_start(None)
    if rc != 0:
        return None, "validator 启动失败，请查看上方输出"
    runtime = _read_runtime()
    if runtime and _probe(runtime["url"]):
        return runtime["url"], None
    return None, "validator 启动后探活失败"


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="内嵌 Legado 验证器生命周期管理")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup-jre", help="检测/下载 Java 21+")
    sub.add_parser("start", help="启动 validator")
    sub.add_parser("stop", help="停止 validator")
    sub.add_parser("status", help="查看运行状态")
    args = parser.parse_args()

    handlers = {
        "setup-jre": cmd_setup_jre,
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

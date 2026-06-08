#!/usr/bin/env python3
"""
局域网文件共享服务
在同一 Wi-Fi 下的任何设备浏览器中上传和下载文件。

模块化结构：
  file_server.py   — 主入口（Flask 路由、启动）
  config.py        — 全局配置常量
  utils.py         — 工具函数（文件图标、大小格式化、IP 获取）
  templates/
    index.html     — 前端页面模板
  static/
    css/style.css  — 样式表
    js/upload.js   — 上传逻辑（真实进度、超时检测、失败弹窗）
"""

import os
import sys
import time
import logging
import traceback
from datetime import datetime

from flask import (
    Flask, request, redirect, url_for, render_template,
    send_from_directory, flash, abort, jsonify
)
from werkzeug.utils import secure_filename

# ---- 项目内模块 ----
from config import PORT, MAX_CONTENT_LENGTH, BASE_DIR, UPLOAD_DIR, UPLOAD_TIMEOUT
from utils import get_file_icon, format_size, get_local_ip

# ---------------------------------------------------------------------------
# 日志配置 — 终端输出带时间戳和级别
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("file_server")

# ---------------------------------------------------------------------------
# Flask 应用初始化
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _is_xhr() -> bool:
    """判断当前请求是否来自 XMLHttpRequest"""
    return request.headers.get("X-Requested-With", "").lower() == "xmlhttprequest"


def _json_error(msg: str, status: int = 400):
    """返回 JSON 错误响应并记录日志"""
    log.warning("  ↳ %s — %s %s", request.remote_addr, status, msg)
    return jsonify(success=False, error=msg, code=status), status


# ---------------------------------------------------------------------------
# 请求前钩子 — 仅记录上传请求
# ---------------------------------------------------------------------------
@app.before_request
def log_upload_start():
    if request.method == "POST" and request.path == "/upload":
        cl = request.content_length or 0
        log.info(
            "⬆️ 上传请求  客户端=%-15s  大小=%s  文件头=%s",
            request.remote_addr or "?",
            format_size(cl) if cl > 0 else "未知",
            request.headers.get("X-File-Name", ""),
        )


# ---------------------------------------------------------------------------
# 路由：首页
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """首页：列出所有可下载文件"""
    files = []
    for entry in sorted(UPLOAD_DIR.iterdir(), key=lambda e: e.stat().st_mtime, reverse=True):
        if entry.is_file() and not entry.name.startswith("."):
            stat = entry.stat()
            files.append({
                "name": entry.name,
                "size_str": format_size(stat.st_size),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "icon": get_file_icon(entry.name),
            })
    return render_template("index.html", files=files)


# ---------------------------------------------------------------------------
# 路由：上传
# ---------------------------------------------------------------------------
@app.route("/upload", methods=["POST"])
def upload():
    """处理文件上传。XHR 请求返回 JSON，普通表单返回重定向。"""
    t0 = time.time()
    client_ip = request.remote_addr or "?"
    content_length = request.content_length or 0

    # 校验文件是否存在
    if "file" not in request.files:
        return _json_error("未选择文件（缺少 file 字段）", 400)

    file = request.files["file"]
    if not file.filename:
        return _json_error("未选择文件（文件名为空）", 400)

    filename = secure_filename(file.filename) or "unnamed_file"
    save_path = UPLOAD_DIR / filename

    # 避免覆盖：重名时加上序号
    if save_path.exists():
        stem, ext = os.path.splitext(filename)
        counter = 1
        while (UPLOAD_DIR / f"{stem}_{counter}{ext}").exists():
            counter += 1
        filename = f"{stem}_{counter}{ext}"
        save_path = UPLOAD_DIR / filename

    try:
        file.save(str(save_path))
    except OSError as e:
        log.error("  ✕ 写入失败 %s | 客户端=%s | errno=%d %s",
                   save_path, client_ip, e.errno or 0, e.strerror or str(e))
        return _json_error(f"服务器写入文件失败: {e.strerror or '磁盘空间不足?'}", 500)
    except Exception as e:
        log.error("  ✕ 保存异常 %s | 客户端=%s", save_path, client_ip)
        log.error(traceback.format_exc())
        return _json_error(f"服务器保存文件异常: {type(e).__name__}", 500)

    elapsed = time.time() - t0
    saved_size = format_size(save_path.stat().st_size)
    actual_bytes = save_path.stat().st_size

    log.info(
        "  ✓ 上传完成  文件=%-30s  大小=%s  耗时=%.1fs",
        filename, saved_size, elapsed,
    )

    # 检验：如果客户端告知了文件大小，对比保存后的实际大小
    if content_length > 0 and actual_bytes > 0:
        diff_ratio = actual_bytes / content_length
        if diff_ratio < 0.9 or diff_ratio > 1.1:
            log.warning(
                "  ⚠ 大小不匹配  content-length=%s(%d) → actual=%s(%d)",
                format_size(content_length), content_length,
                saved_size, actual_bytes,
            )

    if _is_xhr():
        return jsonify(
            success=True,
            filename=filename,
            size_str=saved_size,
            size_bytes=actual_bytes,
            elapsed=round(elapsed, 1),
            message=f"上传成功: {filename}",
        )

    flash(f"✅ 上传成功: {filename} ({saved_size})", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# 路由：下载
# ---------------------------------------------------------------------------
@app.route("/download/<path:filename>")
def download(filename: str):
    """下载文件（防止目录穿越）"""
    safe_name = secure_filename(filename) or filename
    file_path = UPLOAD_DIR / safe_name

    # 安全检查：确保文件在 BASE_DIR 内
    try:
        file_path.resolve().relative_to(BASE_DIR.resolve())
    except ValueError:
        log.warning("  ⛔ 目录穿越尝试  filename=%s  client=%s", filename, request.remote_addr)
        abort(403)

    if not file_path.is_file():
        flash("文件不存在", "error")
        log.info("  ↓ 下载失败（不存在） file=%s client=%s", safe_name, request.remote_addr)
        return redirect(url_for("index"))

    log.info("  ↓ 下载 file=%s client=%s", safe_name, request.remote_addr)
    return send_from_directory(str(UPLOAD_DIR), safe_name, as_attachment=True)


# ---------------------------------------------------------------------------
# 错误处理
# ---------------------------------------------------------------------------
@app.errorhandler(413)
def too_large(e):
    """文件超过 MAX_CONTENT_LENGTH"""
    limit_mb = MAX_CONTENT_LENGTH // (1024 * 1024)
    log.warning("  ✕ 413 内容过大  client=%s  limit=%dMB  desc=%s",
                request.remote_addr, limit_mb,
                request.headers.get("Content-Length", "?"))
    if _is_xhr():
        return jsonify(
            success=False,
            error=f"文件大小超过服务器限制（{limit_mb}MB），请压缩后重试",
            code=413,
        ), 413
    flash(f"文件过大，单文件上限 {limit_mb} MB", "error")
    return redirect(url_for("index"))


@app.errorhandler(404)
def not_found(e):
    log.info("  ✕ 404  client=%s  path=%s", request.remote_addr, request.path)
    if _is_xhr():
        return jsonify(success=False, error="请求的资源不存在", code=404), 404
    return render_template("index.html", files=[]), 404


@app.errorhandler(500)
def server_error(e):
    log.error("  ✕ 500 内部错误  client=%s", request.remote_addr)
    log.error(traceback.format_exc())
    if _is_xhr():
        return jsonify(success=False, error="服务器内部错误，请查看终端日志", code=500), 500
    flash("服务器内部错误", "error")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    local_ip = get_local_ip()

    print()
    print("=" * 55)
    print("  📡  局域网文件共享服务")
    print("=" * 55)
    print()
    print(f"  本机访问:  http://127.0.0.1:{PORT}")
    print(f"  局域网访问: http://{local_ip}:{PORT}")
    print()
    print(f"  共享目录:  {BASE_DIR}")
    print(f"  单文件上限: {MAX_CONTENT_LENGTH // (1024*1024)} MB")
    print(f"  上传超时:   {UPLOAD_TIMEOUT} 秒（客户端）")
    print()
    print("  同一 Wi-Fi 下的手机 / 电脑 / 平板均可访问")
    print("  按 Ctrl+C 停止服务")
    print("=" * 55)
    print()

    app.run(host="0.0.0.0", port=PORT, debug=False)

"""
工具函数：文件图标、大小格式化、本机 IP 获取
"""

import socket
from pathlib import Path


def get_file_icon(filename: str) -> str:
    """根据扩展名返回文件图标"""
    ext = Path(filename).suffix.lower()
    icon_map = {
        ".pdf": "📄", ".doc": "📝", ".docx": "📝", ".xls": "📊", ".xlsx": "📊",
        ".ppt": "📽️", ".pptx": "📽️",
        ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️", ".svg": "🖼️", ".webp": "🖼️",
        ".mp4": "🎬", ".mov": "🎬", ".avi": "🎬", ".mkv": "🎬",
        ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵", ".aac": "🎵",
        ".zip": "📦", ".rar": "📦", ".7z": "📦", ".tar": "📦", ".gz": "📦",
        ".py": "🐍", ".js": "📜", ".ts": "📜", ".html": "🌐", ".css": "🎨",
        ".txt": "📃", ".md": "📃", ".json": "📃", ".xml": "📃",
        ".exe": "⚙️", ".msi": "⚙️", ".apk": "📱",
        ".iso": "💿",
    }
    return icon_map.get(ext, "📁")


def format_size(size_bytes: int) -> str:
    """人类可读的文件大小"""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    if i == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[i]}"


def get_local_ip() -> str:
    """获取本机局域网 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

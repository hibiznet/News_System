# news_system/updater.py
from __future__ import annotations
import json
import os
import tempfile
import urllib.request
import subprocess
from dataclasses import dataclass
from typing import Optional

from news_system.version import __version__

@dataclass
class UpdateInfo:
    latest: str
    installer_url: str
    notes_url: Optional[str] = None
    force: bool = False

def _parse_version(v: str) -> tuple[int, int, int]:
    # "1.2.3" 형태 가정
    parts = v.strip().split(".")
    parts += ["0"] * (3 - len(parts))
    return (int(parts[0]), int(parts[1]), int(parts[2]))

def is_newer(latest: str, current: str = __version__) -> bool:
    return _parse_version(latest) > _parse_version(current)

def fetch_update_info(version_json_url: str, timeout_sec: int = 8) -> UpdateInfo:
    req = urllib.request.Request(version_json_url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as r:
        payload = json.loads(r.read().decode("utf-8"))
    return UpdateInfo(
        latest=payload["latest"],
        installer_url=payload["installer_url"],
        notes_url=payload.get("notes_url"),
        force=bool(payload.get("force", False)),
    )

def download_installer(url: str) -> str:
    # 임시 파일로 다운로드
    fd, path = tempfile.mkstemp(prefix="News_System_Setup_", suffix=".exe")
    os.close(fd)
    urllib.request.urlretrieve(url, path)
    return path

def run_installer(installer_path: str) -> None:
    # Inno Setup: /VERYSILENT /SUPPRESSMSGBOXES 등 옵션 가능
    subprocess.Popen([installer_path], close_fds=True)


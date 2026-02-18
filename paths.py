# news_system/paths.py
from __future__ import annotations
import os
from pathlib import Path

APP_NAME = "News_System"

def appdata_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d

def data_dir() -> Path:
    d = appdata_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d

def logs_dir() -> Path:
    d = appdata_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d

def config_path() -> Path:
    return appdata_dir() / "config.json"

def ensure_subdirs() -> None:
    appdata_dir()
    data_dir()
    logs_dir()

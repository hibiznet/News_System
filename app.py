from flask import Flask, request, jsonify, send_from_directory, send_file, abort
import json, threading, os, time, re, sys
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
import psutil
import yfinance as yf
import pytz
import feedparser
from pathlib import Path
from PIL import Image
import io

# =========================================================
# 경로/환경 (Installer-friendly)
# =========================================================

APP_NAME = "News_System"
KST = pytz.timezone("Asia/Seoul")

def _get_base_dir() -> Path:
    """
    정적 리소스(overlay/admin/shared)가 들어있는 '설치 폴더' 기준 경로.
    - PyInstaller onedir/onefile 모두 대응
    """
    if getattr(sys, "frozen", False):
        # onedir: sys.executable == ...\News_System.exe
        # onefile: sys._MEIPASS 사용
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return Path(base)
    return Path(__file__).resolve().parent

def _get_appdata_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p

BASE_DIR = _get_base_dir()                 # 설치 폴더 (read-only일 수 있음)
APPDATA_ROOT = _get_appdata_root()         # 쓰기 가능
DATA_ROOT = APPDATA_ROOT / "data"
DATA_ROOT.mkdir(parents=True, exist_ok=True)

# JSON은 AppData\data\overlay\*.json 로 이동
OVERLAY_DATA_DIR = DATA_ROOT / "overlay"
OVERLAY_DATA_DIR.mkdir(parents=True, exist_ok=True)

# 배경이미지는 AppData\data\backgrounds 에 저장
BACKGROUNDS_DIR = DATA_ROOT / "backgrounds"
BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)

# 정적 파일은 설치폴더 overlay/admin 에서 제공
OVERLAY_STATIC_DIR = BASE_DIR / "overlay"
ADMIN_STATIC_DIR = BASE_DIR / "admin"
BACKGROUNDS_STATIC_DIR = BASE_DIR / "backgrounds"  # 로컬 테스트용

SOOP_CLIENT_ID = os.environ.get("SOOP_CLIENT_ID", "").strip()
WORK24_API_KEY = os.getenv("WORK24_API_KEY", "").strip()

# =========================================================
# JSON 파일 경로 (AppData)
# =========================================================
def _p(name: str) -> str:
    return str(OVERLAY_DATA_DIR / name)

THEME_PATH    = _p("theme.json")
BACKGROUND_PATH = _p("background.json")
BACKGROUND_ROTATION_PATH = _p("background_rotation.json")
BREAKING_PATH = _p("breaking.json")
BANNER_PATH   = _p("banner.json")
STOCK_PATH    = _p("stock.json")
NEWS_PATH     = _p("news.json")
LAYOUT_PATH   = _p("layout.json")
LIVE_PATH     = _p("live.json")
ROOKIE_PATH   = _p("rookie.json")
UI_PATH       = _p("ui.json")
SOOP_TOP_PATH = _p("soop_top.json")

JOBS_JP_PATH  = _p("jobs_jp.json")
JOBS_JP_CFG   = _p("jobs_jp_config.json")

JPWX_PATH     = _p("jp_weather.json")
JPWX_CFG      = _p("jp_weather_config.json")

ICN_TERM_PATH = _p("icn_terminals.json")
ICN_CFG       = _p("icn_config.json")
ICN_OUT_PATH  = _p("icn_terminal_view.json")

PANELS_PATH   = _p("panels.json")

# =========================================================
# Flask Factory (런처에서 create_app()로 호출)
# =========================================================
def create_app(data_root: Path | None = None) -> Flask:
    """
    설치형 런처(app_main.py)에서 호출:
      app = create_app(data_root=Path(%LOCALAPPDATA%/News_System/data))
    """
    app = Flask(__name__)

    # data_root를 지정하면 OVERLAY_DATA_DIR 재지정 가능
    # (기본값은 위에서 계산된 AppData/data)
    if data_root is not None:
        # override
        global DATA_ROOT, OVERLAY_DATA_DIR, BACKGROUNDS_DIR, BACKGROUNDS_STATIC_DIR
        DATA_ROOT = Path(data_root)
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        OVERLAY_DATA_DIR = DATA_ROOT / "overlay"
        OVERLAY_DATA_DIR.mkdir(parents=True, exist_ok=True)
        BACKGROUNDS_DIR = DATA_ROOT / "backgrounds"
        BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)
        # 로컬 테스트: backgrounds도 프로젝트 폴더에서 읽기
        BACKGROUNDS_STATIC_DIR = BASE_DIR / "backgrounds"
        BACKGROUNDS_STATIC_DIR.mkdir(parents=True, exist_ok=True)

    register_routes(app)
    return app

# =========================================================
# 유틸: 안전 JSON read/write (atomic)
# =========================================================
def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def _atomic_write_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# =========================================================
# 기본값
# =========================================================
DEFAULT_JOBS_CFG = {
  "source": "tokyodev",     # tokyodev | japandev
  "preset": "td_all",       # preset key
  "ui": {"count": 10, "roll": True, "interval": 30}
}

JOB_SOURCES = {
  "tokyodev": {
    "name": "TokyoDev",
    "presets": {
      "td_all":      {"name": "🇯🇵 TokyoDev - 전체",      "url": "https://www.tokyodev.com/jobs"},
      "td_backend":  {"name": "🇯🇵 TokyoDev - Backend",   "url": "https://www.tokyodev.com/jobs/backend"},
      "td_frontend": {"name": "🇯🇵 TokyoDev - Frontend",  "url": "https://www.tokyodev.com/jobs/frontend"},
    }
  },
  "japandev": {
    "name": "Japan Dev",
    "presets": {
      "jd_all":        {"name": "🇯🇵 Japan Dev - 전체",           "url": "https://japan-dev.com/jobs"},
      "jd_tokyo":      {"name": "🇯🇵 Japan Dev - 도쿄",           "url": "https://japan-dev.com/jobs-in-tokyo"},
      "jd_relocation": {"name": "🇯🇵 Japan Dev - 비자/리로케이션", "url": "https://japan-dev.com/japan-jobs-relocation"},
    }
  }
}

# DEFAULT_PANELS의 { ... } 부분은 원본에서 실제 값으로 채워야 합니다.
# 일단 안전하게 최소 형태로 둡니다.
DEFAULT_PANELS = {
  "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
  "resetToken": 0,
  "panels": {
    "jobsjp": {"enabled": True, "width": 360, "opacity": 0.22, "fontSize": 13},
    "jpwx":   {"enabled": True, "width": 360, "opacity": 0.22, "fontSize": 13},
    "icn":    {"enabled": True, "width": 360, "opacity": 0.22, "fontSize": 13}
  }
}

# =========================================================
# System Metrics Sampler (start_background_jobs에서 시작)
# =========================================================
METRICS_CACHE = {
    "ts": time.time(),
    "cpu": 0.0,
    "cpu_percore": [],
    "mem": 0.0,
    "mem_used": 0,
    "mem_total": 0,
    "disk": None,
    "net_up_bps": 0.0,
    "net_down_bps": 0.0,
    "top_procs": []
}
_metrics_lock = threading.Lock()

def _safe_disk_usage():
    try:
        if os.name == "nt":
            return psutil.disk_usage("C:\\").percent
        return psutil.disk_usage("/").percent
    except:
        return None

def metrics_loop():
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)

    for p in psutil.process_iter(attrs=["pid"]):
        try:
            p.cpu_percent(interval=None)
        except:
            pass

    last_net = psutil.net_io_counters()
    last_ts = time.time()

    while True:
        now = time.time()
        dt = max(0.001, now - last_ts)

        cpu_total = psutil.cpu_percent(interval=None)
        cpu_cores = psutil.cpu_percent(interval=None, percpu=True)

        vm = psutil.virtual_memory()
        disk_pct = _safe_disk_usage()

        net = psutil.net_io_counters()
        up_bps = (net.bytes_sent - last_net.bytes_sent) / dt
        down_bps = (net.bytes_recv - last_net.bytes_recv) / dt
        last_net, last_ts = net, now

        procs = []
        for p in psutil.process_iter(attrs=["pid", "name"]):
            try:
                cpu_p = p.cpu_percent(interval=None)
                mem_mb = (p.memory_info().rss / (1024 * 1024))
                if cpu_p > 0.0 or mem_mb > 50:
                    procs.append({
                        "pid": p.info.get("pid"),
                        "name": p.info.get("name") or "unknown",
                        "cpu": round(cpu_p, 1),
                        "mem_mb": round(mem_mb, 1)
                    })
            except:
                continue

        procs.sort(key=lambda x: (x["cpu"], x["mem_mb"]), reverse=True)
        top5 = procs[:5]

        with _metrics_lock:
            METRICS_CACHE.update({
                "ts": now,
                "cpu": cpu_total,
                "cpu_percore": cpu_cores,
                "mem": vm.percent,
                "mem_used": vm.used,
                "mem_total": vm.total,
                "disk": disk_pct,
                "net_up_bps": up_bps,
                "net_down_bps": down_bps,
                "top_procs": top5
            })

        time.sleep(1)

# =========================================================
# 정적 파일 라우팅
# - HTML/CSS/JS: 설치폴더 overlay/admin에서 제공
# - JSON: AppData overlay에서 제공 (동일 URL로 호환)
# =========================================================
def register_routes(app: Flask) -> None:
    @app.route("/")
    def root():
        # overlay/index.html은 설치 폴더에서
        return send_from_directory(str(OVERLAY_STATIC_DIR), "index.html")

    @app.route("/overlay/<path:path>")
    def overlay_files(path):
        # JSON은 AppData에서 제공
        if path.lower().endswith(".json"):
            p = OVERLAY_DATA_DIR / path
            if not p.exists():
                abort(404)
            return send_from_directory(str(OVERLAY_DATA_DIR), path)

        # 그 외 정적 파일은 설치 폴더에서 제공
        return send_from_directory(str(OVERLAY_STATIC_DIR), path)

    @app.route("/admin/<path:path>")
    def admin_files(path):
        return send_from_directory(str(ADMIN_STATIC_DIR), path)
    
    # ✅ 루트(/)에서 참조되는 정적 파일들(style.css, script.js 등)을 overlay 폴더에서 서빙
    @app.route("/<path:path>")
    def root_assets(path):
        # 1) JSON은 AppData overlay에서 (루트로 요청되는 경우도 커버)
        if path.lower().endswith(".json"):
            p = OVERLAY_DATA_DIR / path
            if p.exists():
                return send_from_directory(str(OVERLAY_DATA_DIR), path)
            abort(404)

        # 2) 나머지 정적 파일은 설치폴더 overlay에서
        p = OVERLAY_STATIC_DIR / path
        if p.exists():
            return send_from_directory(str(OVERLAY_STATIC_DIR), path)

        # 3) admin 정적이 루트로 잘못 요청되는 경우까지 커버(선택)
        p2 = ADMIN_STATIC_DIR / path
        if p2.exists():
            return send_from_directory(str(ADMIN_STATIC_DIR), path)

        abort(404)

    # =========================
    # API: breaking
    # =========================
    @app.route("/api/breaking", methods=["POST"])
    def breaking():
        data = request.json or {}
        text = data.get("text", "")
        expire = data.get("expire", 0)

        _atomic_write_json(BREAKING_PATH, {"text": text})

        if expire and expire > 0:
            threading.Timer(expire * 60, clear_breaking).start()

        return jsonify(ok=True)

    @app.route("/api/clear", methods=["POST"])
    def clear_breaking():
        _atomic_write_json(BREAKING_PATH, {"text": ""})
        return jsonify(ok=True)

    # =========================
    # API: banner
    # =========================
    @app.route("/api/banner", methods=["POST"])
    def banner():
        data = request.json or {}
        text = data.get("text", "")
        expire = data.get("expire", 0)

        _atomic_write_json(BANNER_PATH, {"text": text})

        if expire and expire > 0:
            threading.Timer(expire * 60, clear_banner).start()

        return jsonify(ok=True)

    @app.route("/api/banner/clear", methods=["POST"])
    def clear_banner():
        _atomic_write_json(BANNER_PATH, {"text": ""})
        return jsonify(ok=True)

    # =========================
    # API: theme
    # =========================
    @app.route("/api/theme", methods=["POST"])
    def theme_set():
        data = request.json or {}
        _atomic_write_json(THEME_PATH, data)
        return jsonify(ok=True)

    @app.route("/api/theme/clear", methods=["POST"])
    def theme_clear():
        _atomic_write_json(THEME_PATH, {})
        return jsonify(ok=True)

    # =========================
    # API: background
    # =========================
    @app.route("/api/backgrounds/list", methods=["GET"])
    def backgrounds_list():
        """배경이미지 폴더 내 이미지 파일 목록 반환"""
        try:
            files = []
            if BACKGROUNDS_STATIC_DIR.exists():
                # 이미지 파일 확장자
                image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
                for f in sorted(BACKGROUNDS_STATIC_DIR.iterdir()):
                    if f.is_file() and f.suffix.lower() in image_exts:
                        files.append(f.name)
            return jsonify(files=files)
        except Exception as e:
            return jsonify(error=str(e)), 500

    @app.route("/api/backgrounds/thumbnail/<filename>", methods=["GET"])
    def backgrounds_thumbnail(filename: str):
        """배경이미지 썸네일 제공 (최대 200x150)"""
        try:
            # 보안: 파일명에 .. 등이 포함되지 않도록 필터
            if ".." in filename or "/" in filename or "\\" in filename:
                return abort(400)
            
            filepath = BACKGROUNDS_STATIC_DIR / filename
            if not filepath.exists() or not filepath.is_file():
                return abort(404)
            
            # 이미지 열기
            img = Image.open(filepath)
            # 썸네일 생성 (200x150)
            img.thumbnail((200, 150), Image.Resampling.LANCZOS)
            
            # 메모리에 저장
            img_io = io.BytesIO()
            img.save(img_io, format="PNG")
            img_io.seek(0)
            
            return send_file(img_io, mimetype="image/png", download_name=None)
        except Exception as e:
            return jsonify(error=str(e)), 500

    @app.route("/api/backgrounds/image/<filename>", methods=["GET"])
    def backgrounds_image(filename: str):
        """전체 배경이미지 제공"""
        try:
            if ".." in filename or "/" in filename or "\\" in filename:
                return abort(400)
            
            filepath = BACKGROUNDS_STATIC_DIR / filename
            if not filepath.exists() or not filepath.is_file():
                return abort(404)
            
            return send_file(str(filepath), download_name=None)
        except Exception as e:
            return jsonify(error=str(e)), 500

    @app.route("/api/backgrounds/set", methods=["POST"])
    def backgrounds_set():
        """선택한 배경이미지 저장"""
        try:
            data = request.json or {}
            filename = str(data.get("filename", "")).strip()
            
            if not filename or ".." in filename or "/" in filename or "\\" in filename:
                return jsonify(error="Invalid filename"), 400
            
            filepath = BACKGROUNDS_STATIC_DIR / filename

            if not filepath.exists():
                return jsonify(error="File not found"), 404
            
            # background.json에 저장
            _atomic_write_json(BACKGROUND_PATH, {"current": filename})
            return jsonify(ok=True, current=filename)
        except Exception as e:
            return jsonify(error=str(e)), 500

    @app.route("/api/backgrounds/rotation/config", methods=["GET"])
    def backgrounds_rotation_config_get():
        """배경이미지 자동 회전 설정 조회"""
        try:
            cfg = _read_json(BACKGROUND_ROTATION_PATH, {})
            return jsonify(
                enabled=cfg.get("enabled", False),
                interval_minutes=cfg.get("interval_minutes", 15)
            )
        except Exception as e:
            return jsonify(error=str(e)), 500

    @app.route("/api/backgrounds/rotation/config", methods=["POST"])
    def backgrounds_rotation_config_set():
        """배경이미지 자동 회전 설정 변경"""
        try:
            data = request.json or {}
            enabled = data.get("enabled", False)
            interval_minutes = int(data.get("interval_minutes", 15))
            
            # 1~120분 범위 제약
            interval_minutes = max(1, min(120, interval_minutes))
            
            cfg = {
                "enabled": enabled,
                "interval_minutes": interval_minutes
            }
            _atomic_write_json(BACKGROUND_ROTATION_PATH, cfg)
            print(f"[BACKGROUND ROTATION CONFIG] enabled={enabled}, interval={interval_minutes}분")
            return jsonify(ok=True, config=cfg)
        except Exception as e:
            return jsonify(error=str(e)), 500

    @app.route("/api/backgrounds/rotation/next", methods=["POST"])
    def backgrounds_rotation_next():
        """다음 배경이미지로 즉시 전환"""
        try:
            rotate_background()
            current = _read_json(BACKGROUND_PATH, {})
            return jsonify(ok=True, current=current.get("current", ""))
        except Exception as e:
            return jsonify(error=str(e)), 500

    # =========================
    # Debug: 경로 확인
    # =========================
    @app.route("/debug/paths", methods=["GET"])
    def debug_paths():
        """로컬 테스트 시 경로 확인용"""
        return jsonify(
            base_dir=str(BASE_DIR),
            appdata_root=str(APPDATA_ROOT),
            data_root=str(DATA_ROOT),
            overlay_static_dir=str(OVERLAY_STATIC_DIR),
            overlay_data_dir=str(OVERLAY_DATA_DIR),
            backgrounds_static_dir=str(BACKGROUNDS_STATIC_DIR),
            backgrounds_exists=BACKGROUNDS_STATIC_DIR.exists(),
            backgrounds_files=[f.name for f in sorted(BACKGROUNDS_STATIC_DIR.iterdir()) if f.is_file()] if BACKGROUNDS_STATIC_DIR.exists() else []
        )

    # =========================
    # API: layout
    # =========================
    @app.route("/api/layout", methods=["POST"])
    def layout_set():
        data = request.json or {}
        mode = int(data.get("mode", 1))
        if mode not in (1, 2, 4):
            mode = 1

        items = data.get("items", [])
        if not isinstance(items, list):
            items = []

        fixed = []
        for i in range(4):
            src = ""
            if i < len(items) and isinstance(items[i], dict):
                src = str(items[i].get("src", "")).strip()
            fixed.append({"src": src})

        out = {"mode": mode, "items": fixed}
        _atomic_write_json(LAYOUT_PATH, out)
        return jsonify(ok=True)

    @app.route("/api/layout/clear", methods=["POST"])
    def layout_clear():
        out = {"mode": 1, "items": [{"src": ""}, {"src": ""}, {"src": ""}, {"src": ""}]}
        _atomic_write_json(LAYOUT_PATH, out)
        return jsonify(ok=True)

    # =========================
    # API: live
    # =========================
    @app.route("/api/live", methods=["POST"])
    def live_set():
        data = request.json or {}
        enabled = bool(data.get("enabled", True))
        mode = str(data.get("mode", "live")).lower()
        if mode not in ("live", "recorded", "off"):
            mode = "live"
        text = str(data.get("text", "")).strip()

        out = {"enabled": enabled, "mode": mode, "text": text}
        _atomic_write_json(LIVE_PATH, out)
        return jsonify(ok=True)

    # =========================
    # API: ui floating
    # =========================
    @app.route("/api/ui/floating/show", methods=["POST"])
    def ui_floating_show():
        data = _read_json(UI_PATH, {"floatingMenu": {"hidden": False}})
        if "floatingMenu" not in data:
            data["floatingMenu"] = {}
        data["floatingMenu"]["hidden"] = False
        _atomic_write_json(UI_PATH, data)
        return jsonify(ok=True)

    @app.route("/api/ui/floating/hide", methods=["POST"])
    def ui_floating_hide():
        data = _read_json(UI_PATH, {"floatingMenu": {"hidden": True}})
        if "floatingMenu" not in data:
            data["floatingMenu"] = {}
        data["floatingMenu"]["hidden"] = True
        _atomic_write_json(UI_PATH, data)
        return jsonify(ok=True)

    # =========================
    # API: jobsjp presets/config
    # =========================
    @app.route("/api/jobsjp/presets", methods=["GET"])
    def jobsjp_presets():
        cfg = load_jobs_cfg_full()
        sources = []
        for sk, sv in JOB_SOURCES.items():
            sources.append({
                "key": sk,
                "name": sv["name"],
                "presets": [{"key": pk, "name": pv["name"]} for pk, pv in sv["presets"].items()]
            })
        return jsonify(ok=True, sources=sources, current=cfg)

    @app.route("/api/jobsjp/config", methods=["POST"])
    def jobsjp_config():
        req = request.json or {}
        cfg = load_jobs_cfg_full()

        source = req.get("source", cfg["source"])
        if source not in JOB_SOURCES:
            source = cfg["source"]

        preset = req.get("preset", cfg["preset"])
        if preset not in JOB_SOURCES[source]["presets"]:
            preset = next(iter(JOB_SOURCES[source]["presets"].keys()))

        ui = req.get("ui", cfg["ui"])
        if not isinstance(ui, dict):
            ui = cfg["ui"]

        cfg = {"source": source, "preset": preset, "ui": cfg["ui"]}
        try: cfg["ui"]["count"] = max(1, min(10, int(ui.get("count", cfg["ui"]["count"]))))
        except: pass
        cfg["ui"]["roll"] = bool(ui.get("roll", cfg["ui"]["roll"]))
        try: cfg["ui"]["interval"] = max(3, min(300, int(ui.get("interval", cfg["ui"]["interval"]))))
        except: pass

        save_jobs_cfg(cfg)

        # 즉시 1회 갱신
        update_jobs_jp()
        return jsonify(ok=True, current=cfg)

    # =========================
    # API: metrics
    # =========================
    @app.route("/api/metrics", methods=["GET"])
    def metrics():
        with _metrics_lock:
            return jsonify(METRICS_CACHE)

    # =========================
    # API: icn config
    # =========================
    @app.route("/api/icn/config", methods=["POST"])
    def icn_config():
        cfg = _read_json(ICN_CFG, {"enabled": True, "ui": {"show": 12, "query": ""}})
        req = request.json or {}
        cfg["enabled"] = bool(req.get("enabled", cfg.get("enabled", True)))
        ui = req.get("ui", cfg.get("ui", {}))
        if isinstance(ui, dict):
            cfg["ui"]["query"] = str(ui.get("query", cfg["ui"].get("query","")))
            try: cfg["ui"]["show"] = max(1, min(50, int(ui.get("show", cfg["ui"].get("show",12)))))
            except: pass

        _atomic_write_json(ICN_CFG, cfg)
        update_icn_terminal_view()
        return jsonify(ok=True, current=cfg)

    # =========================
    # API: panels
    # =========================
    @app.route("/api/panels", methods=["GET"])
    def get_panels():
        data = _read_json(PANELS_PATH, DEFAULT_PANELS)
        return jsonify(ok=True, data=data)

    @app.route("/api/panels", methods=["POST"])
    def save_panels():
        req = request.json or {}
        data = _read_json(PANELS_PATH, DEFAULT_PANELS)

        panels = req.get("panels", {})
        if not isinstance(panels, dict):
            panels = {}

        for key in ["jobsjp", "jpwx", "icn"]:
            cur = data["panels"].get(key, {})
            upd = panels.get(key, {})
            if not isinstance(upd, dict):
                upd = {}

            enabled = bool(upd.get("enabled", cur.get("enabled", True)))
            try: width = max(240, min(520, int(upd.get("width", cur.get("width", 360)))))
            except: width = cur.get("width", 360)
            try: opacity = float(upd.get("opacity", cur.get("opacity", 0.22)))
            except: opacity = cur.get("opacity", 0.22)
            opacity = max(0.05, min(0.9, opacity))
            try: fontSize = max(10, min(20, int(upd.get("fontSize", cur.get("fontSize", 13)))))
            except: fontSize = cur.get("fontSize", 13)

            data["panels"][key] = {"enabled": enabled, "width": width, "opacity": opacity, "fontSize": fontSize}

        data["updated"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
        _atomic_write_json(PANELS_PATH, data)
        return jsonify(ok=True, data=data)

    @app.route("/api/panels/reset", methods=["POST"])
    def panels_reset():
        data = _read_json(PANELS_PATH, DEFAULT_PANELS)
        # when resetting we want any panels that were disabled to come back
        for key, p in data.get("panels", {}).items():
            if isinstance(p, dict):
                p["enabled"] = True

        data["resetToken"] = int(data.get("resetToken", 0)) + 1
        data["updated"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
        _atomic_write_json(PANELS_PATH, data)
        return jsonify(ok=True, resetToken=data["resetToken"])


# =========================================================
# 주식/뉴스/soop/rookie/jobs/weather/icn 업데이트 로직
# (원본 기능을 그대로 유지하되 write는 AppData로)
# =========================================================

SYMBOLS = {
    "domestic": {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"},
    "global": {"NASDAQ": "^IXIC", "DOW": "^DJI", "S&P500": "^GSPC"}
}

def update_stock():
    result = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "domestic": {},
        "global": {}
    }
    for group, items in SYMBOLS.items():
        for name, symbol in items.items():
            try:
                t = yf.Ticker(symbol)
                info = t.fast_info
                price = round(info["last_price"], 2)
                prev  = info["previous_close"]
                change = round(((price - prev) / prev) * 100, 2)
                result[group][name] = {"price": price, "change": change}
            except Exception:
                result[group][name] = {"price": None, "change": None}

    _atomic_write_json(STOCK_PATH, result)
    print("[STOCK UPDATED]", result["updated"])

def stock_loop():
    while True:
        update_stock()
        time.sleep(300)

def rotate_background():
    """배경이미지 자동 회전 함수"""
    try:
        # 회전 설정 로드
        cfg = _read_json(BACKGROUND_ROTATION_PATH, {})
        if not cfg.get("enabled", False):
            return
        
        # 배경 이미지 파일 목록 가져오기
        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        files = []
        if BACKGROUNDS_STATIC_DIR.exists():
            for f in sorted(BACKGROUNDS_STATIC_DIR.iterdir()):
                if f.is_file() and f.suffix.lower() in image_exts:
                    files.append(f.name)
        
        if len(files) < 2:
            # 이미지 1개 이하면 회전 불가
            return
        
        # 현재 배경 확인
        current = _read_json(BACKGROUND_PATH, {})
        current_file = current.get("current", "")
        
        # 다음 이미지 선택 (순환)
        if current_file in files:
            idx = files.index(current_file)
            next_file = files[(idx + 1) % len(files)]
        else:
            next_file = files[0]
        
        # 다음 배경으로 변경
        _atomic_write_json(BACKGROUND_PATH, {"current": next_file})
        print(f"[BACKGROUND ROTATED] {next_file}")
    
    except Exception as e:
        print(f"[BACKGROUND ROTATION ERROR] {e}")

def background_rotation_loop():
    """배경이미지 자동 회전 루프"""
    while True:
        try:
            cfg = _read_json(BACKGROUND_ROTATION_PATH, {})
            interval_minutes = cfg.get("interval_minutes", 15)
            # 10~20분 범위 제약
            interval_minutes = max(1, min(120, interval_minutes))  # 1~120분
            
            rotate_background()
            time.sleep(interval_minutes * 60)
        except Exception as e:
            print(f"[BACKGROUND ROTATION LOOP ERROR] {e}")
            time.sleep(60)  # 에러시 1분 대기 후 재시도

RSS_URL = "https://www.yna.co.kr/rss/news.xml"
MAX_NEWS_ITEMS = 5

def clean_title(title: str) -> str:
    remove_words = ["종합", "속보", "단독", "포토", "영상", "[속보]", "[단독]", "(종합)"]
    for word in remove_words:
        title = title.replace(word, "")
    return title.strip()

def update_news():
    try:
        feed = feedparser.parse(RSS_URL)
        items = [clean_title(e.title) for e in feed.entries[:MAX_NEWS_ITEMS]]
        output = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "items": items
        }
        _atomic_write_json(NEWS_PATH, output)
        print(f"[NEWS UPDATED] {output['updated']} ({len(items)}건)")
    except Exception as e:
        print("[NEWS ERROR]", e)

def news_loop():
    while True:
        update_news()
        time.sleep(300)

def _write_soop_top_empty(reason="disabled"):
    out = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "items": [],
        "disabled": True,
        "reason": reason
    }
    _atomic_write_json(SOOP_TOP_PATH, out)

def _parse_jsonp(text: str):
    m = re.search(r'^[a-zA-Z0-9_]+\((.*)\)\s*;?\s*$', text.strip(), re.DOTALL)
    return json.loads(m.group(1)) if m else json.loads(text)

def update_soop_top():
    if not SOOP_CLIENT_ID:
        _write_soop_top_empty("missing_client_id")
        return

    url = "https://openapi.sooplive.co.kr/broad/list"
    params = {"client_id": SOOP_CLIENT_ID, "order_type": "view_cnt", "page_no": 1, "callback": "cb"}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        payload = _parse_jsonp(r.text)

        if int(payload.get("result", 0)) <= 0:
            _write_soop_top_empty(f"api_error:{payload.get('result')}:{payload.get('msg')}")
            return

        broads = (payload.get("broad") or [])[:5]
        items = []
        for i, b in enumerate(broads, start=1):
            items.append({
                "rank": i,
                "user_id": b.get("user_id"),
                "user_nick": b.get("user_nick"),
                "broad_no": b.get("broad_no"),
                "title": b.get("broad_title"),
                "view_cnt": int(b.get("total_view_cnt") or 0),
            })

        out = {"updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "items": items}
        _atomic_write_json(SOOP_TOP_PATH, out)

    except Exception as e:
        _write_soop_top_empty(f"exception:{type(e).__name__}")

def soop_top_loop():
    while True:
        update_soop_top()
        time.sleep(60)

ROOKIE_API_URL = "https://afevent2.sooplive.co.kr/app/rank/api.php"

def update_rookie():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/javascript, */*;q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://afevent2.sooplive.co.kr",
            "Referer": "https://afevent2.sooplive.co.kr/app/rank/index.php?szWhich=rookie",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        payload = {"szWhich": "rookie", "nPage": "1", "szSearch": "", "szGender": "A"}

        r = requests.post(ROOKIE_API_URL, headers=headers, data=payload, timeout=12)
        r.raise_for_status()
        data = r.json()

        arr = data.get("ALL_RANK") or []
        if not isinstance(arr, list) or len(arr) == 0:
            out = {
                "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "items": [],
                "disabled": True,
                "reason": "api_all_rank_empty",
                "debug": {"RESULT": data.get("RESULT"), "TOTAL_CNT": data.get("TOTAL_CNT")}
            }
            _atomic_write_json(ROOKIE_PATH, out)
            return

        items = []
        for it in arr[:10]:
            bj_id = str(it.get("bj_id", "")).strip()
            bj_nick = str(it.get("bj_nick", "")).strip()
            station_title = str(it.get("station_title", "")).strip()
            is_broad = bool(it.get("is_broad", False))

            try: rank_now = int(it.get("total_rank") or 0)
            except: rank_now = 0
            try: rank_last = int(it.get("total_rank_last") or 0)
            except: rank_last = 0

            move = "same"
            delta = None
            if rank_now > 0 and rank_last > 0:
                diff = rank_last - rank_now
                if diff > 0:
                    move, delta = "up", diff
                elif diff < 0:
                    move, delta = "down", abs(diff)
            elif rank_now > 0 and rank_last == 0:
                move, delta = "new", None

            items.append({
                "rank": rank_now if rank_now > 0 else len(items) + 1,
                "name": bj_nick or bj_id,
                "bj_id": bj_id,
                "title": station_title,
                "is_live": is_broad,
                "move": move,
                "delta": delta
            })

        items.sort(key=lambda x: x["rank"])
        items = items[:10]

        out = {"updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "items": items}
        _atomic_write_json(ROOKIE_PATH, out)
        print("[ROOKIE UPDATED]", out["updated"], "items:", len(items))

    except Exception as e:
        out = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "items": [],
            "disabled": True,
            "reason": f"exception:{type(e).__name__}"
        }
        _atomic_write_json(ROOKIE_PATH, out)

def rookie_loop():
    while True:
        update_rookie()
        time.sleep(300)

# --- Jobs JP (원본 함수들 유지, write만 atomic) ---

def load_jobs_cfg_full():
    cfg = _read_json(JOBS_JP_CFG, DEFAULT_JOBS_CFG.copy())
    if not isinstance(cfg, dict):
        cfg = DEFAULT_JOBS_CFG.copy()

    source = cfg.get("source", "tokyodev")
    if source not in JOB_SOURCES:
        source = "tokyodev"

    presets = JOB_SOURCES[source]["presets"]
    preset = cfg.get("preset")
    if preset not in presets:
        preset = next(iter(presets.keys()))

    ui = cfg.get("ui") if isinstance(cfg.get("ui"), dict) else {}
    try: count = int(ui.get("count", 10))
    except: count = 10
    count = max(1, min(10, count))

    roll = bool(ui.get("roll", True))
    try: interval = int(ui.get("interval", 30))
    except: interval = 30
    interval = max(3, min(300, interval))

    return {"source": source, "preset": preset, "ui": {"count": count, "roll": roll, "interval": interval}}

def save_jobs_cfg(cfg):
    _atomic_write_json(JOBS_JP_CFG, cfg)

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def _guess_jp_required(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["business japanese", "fluent japanese", "jlpt n1", "jlpt n2", "native japanese"]):
        return "required"
    if any(k in t for k in ["japanese preferred", "nice to have japanese", "japanese a plus"]):
        return "preferred"
    if any(k in t for k in ["no japanese", "english only", "japanese not required"]):
        return "not_required"
    return ""

def _extract_salary(text: str) -> str:
    t = text or ""
    m = re.search(r"(¥\s?\d[\d\.\,]*\s?[mk]?\s?~\s?¥\s?\d[\d\.\,]*\s?[mk]?)", t, re.I)
    if m: return _clean(m.group(1))
    m = re.search(r"(¥\s?\d[\d\.\,]*\s?[mk]?)", t, re.I)
    if m: return _clean(m.group(1))
    m = re.search(r"(\$\s?\d[\d\.\,]*\s?[k]?\s?~\s?\$\s?\d[\d\.\,]*\s?[k]?)", t, re.I)
    if m: return _clean(m.group(1))
    m = re.search(r"(\$\s?\d[\d\.\,]*\s?[k]?)", t, re.I)
    if m: return _clean(m.group(1))
    return ""

def _extract_company(card, fallback_text: str) -> str:
    try:
        for attr in ["data-company", "data-employer", "data-company-name"]:
            v = card.get(attr)
            if v and len(v) <= 60:
                return _clean(v)
    except:
        pass
    m = re.search(r"\bat\s+([A-Za-z0-9\-\&\.\s]{2,40})", fallback_text or "")
    if m:
        return _clean(m.group(1))
    return ""

def _extract_location(card_text: str) -> str:
    t = (card_text or "").lower()
    if "remote" in t: return "Remote"
    if "tokyo" in t: return "Tokyo"
    if "osaka" in t: return "Osaka"
    if "japan" in t: return "Japan"
    return ""

def _collect_tags(card) -> list:
    tags = []
    if not card:
        return tags
    for node in card.select("span, li, div"):
        txt = _clean(node.get_text(" ", strip=True))
        if 2 <= len(txt) <= 28 and txt not in tags:
            low = txt.lower()
            if low in ["apply", "learn more", "view", "jobs", "job"]:
                continue
            tags.append(txt)
        if len(tags) >= 10:
            break
    return tags

def fetch_tokyodev_struct(url: str, limit: int = 30) -> list:
    r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    items, seen = [], set()
    for a in soup.select('a[href^="/jobs/"]'):
        href = a.get("href", "")
        if href.count("/") < 2:
            continue
        if href in ["/jobs/backend", "/jobs/frontend", "/jobs"]:
            continue

        link = urljoin("https://www.tokyodev.com", href)
        h = a.select_one("h2,h3")
        title = _clean(h.get_text(" ", strip=True)) if h else _clean(a.get_text(" ", strip=True))
        if not title or len(title) < 10:
            continue

        card = a.find_parent("article") or a.find_parent(["li","div"])
        if not card:
            continue

        card_text = _clean(card.get_text(" ", strip=True))

        tags = []
        for chip in card.select("span, a, div"):
            t = _clean(chip.get_text(" ", strip=True))
            if 2 <= len(t) <= 28 and t not in tags:
                low = t.lower()
                if low in ["apply", "learn more", "view"]:
                    continue
                tags.append(t)
            if len(tags) >= 8:
                break

        salary = _extract_salary(card_text)
        jpRequired = _guess_jp_required(" ".join(tags) + " " + card_text)
        location = _extract_location(" ".join(tags) + " " + card_text)
        company = _extract_company(card, card_text) or ""

        key = (title, link)
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "title": title,
            "company": company,
            "salary": salary,
            "location": location,
            "jpRequired": jpRequired,
            "tags": tags,
            "link": link
        })
        if len(items) >= limit:
            break

    return items

def fetch_japandev_struct(url: str, limit: int = 30) -> list:
    r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    items, seen = [], set()
    for a in soup.select('a[href*="/jobs/"]'):
        href = a.get("href", "")
        link = urljoin("https://japan-dev.com", href)

        title = _clean(a.get_text(" ", strip=True))
        if not title or len(title) < 6:
            continue

        card = a.find_parent(["article", "li", "div"]) or a.parent
        card_text = _clean(card.get_text(" ", strip=True)) if card else title

        salary = _extract_salary(card_text)
        tags = _collect_tags(card)
        jpRequired = _guess_jp_required(card_text + " " + " ".join(tags))
        location = _extract_location(card_text + " " + " ".join(tags))
        company = _extract_company(card, card_text) or ""

        key = (title, link)
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "title": title,
            "company": company,
            "salary": salary,
            "location": location,
            "jpRequired": jpRequired,
            "tags": tags,
            "link": link
        })
        if len(items) >= limit:
            break
    return items

def update_jobs_jp():
    cfg = load_jobs_cfg_full()
    source = cfg["source"]
    preset_key = cfg["preset"]

    preset = JOB_SOURCES[source]["presets"][preset_key]
    url = preset["url"]
    preset_name = f"{JOB_SOURCES[source]['name']} · {preset['name']}"

    last = _read_json(JOBS_JP_PATH, {"items": []})
    last_items = last.get("items", []) if isinstance(last, dict) else []
    if not isinstance(last_items, list):
        last_items = []
    
    # panels.json에서 enabled 상태를 읽어서 보존 (사용자가 패널을 닫은 상태 유지)
    panels_data = _read_json(PANELS_PATH, DEFAULT_PANELS)
    last_enabled = panels_data.get("panels", {}).get("jobsjp", {}).get("enabled", True)

    try:
        sourceName = JOB_SOURCES[source]["name"]

        if source == "tokyodev":
            items = fetch_tokyodev_struct(url, limit=30)
            items = [it for it in items if it.get("title") and len(it["title"]) >= 10]
            if not items:
                fb = JOB_SOURCES["japandev"]["presets"]["jd_all"]["url"]
                items = fetch_japandev_struct(fb, limit=30)
                preset_name += " (fallback: Japan Dev)"
                sourceName = "Japan Dev (fallback)"
        else:
            items = fetch_japandev_struct(url, limit=30)
            if not items:
                fb = JOB_SOURCES["tokyodev"]["presets"]["td_all"]["url"]
                items = fetch_tokyodev_struct(fb, limit=30)
                preset_name += " (fallback: TokyoDev)"
                sourceName = "TokyoDev (fallback)"

        if not items:
            out = {
                "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "preset": preset_key,
                "presetName": preset_name,
                "sourceName": sourceName,
                "ui": cfg["ui"],
                "items": last_items,
                "enabled": last_enabled,
                "disabled": False,
                "warn": "parsed_but_empty",
                "debug": {"url": url}
            }
        else:
            out = {
                "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "preset": preset_key,
                "presetName": preset_name,
                "sourceName": sourceName,
                "ui": cfg["ui"],
                "items": items,
                "enabled": last_enabled
            }

        _atomic_write_json(JOBS_JP_PATH, out)
        print("[JOBS UPDATED]", out["updated"], preset_key, "items:", len(out["items"]))

    except Exception as e:
        out = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "preset": preset_key,
            "presetName": preset_name,
            "sourceName": JOB_SOURCES[source]["name"],
            "ui": cfg["ui"],
            "items": last_items,
            "enabled": last_enabled,
            "disabled": False,
            "warn": f"exception:{type(e).__name__}",
            "debug": {"url": url}
        }
        _atomic_write_json(JOBS_JP_PATH, out)

def jobs_jp_loop():
    while True:
        update_jobs_jp()
        time.sleep(1800)

# --- JP Weather ---

JP_CITIES = [
    {"key":"tokyo", "name":"도쿄", "lat":35.6762, "lon":139.6503},
    {"key":"osaka", "name":"오사카", "lat":34.6937, "lon":135.5023},
    {"key":"fukuoka", "name":"후쿠오카", "lat":33.5904, "lon":130.4017},
]

WMO_MAP = {
  0:("맑음","☀️"), 1:("대체로 맑음","🌤️"), 2:("구름조금","⛅"), 3:("흐림","☁️"),
  45:("안개","🌫️"), 48:("서리안개","🌫️"),
  51:("이슬비","🌦️"), 53:("이슬비","🌦️"), 55:("이슬비","🌦️"),
  61:("비","🌧️"), 63:("비","🌧️"), 65:("폭우","🌧️"),
  71:("눈","🌨️"), 73:("눈","🌨️"), 75:("폭설","🌨️"),
  80:("소나기","🌦️"), 81:("소나기","🌦️"), 82:("강한 소나기","🌧️"),
  95:("뇌우","⛈️"), 96:("우박뇌우","⛈️"), 99:("우박뇌우","⛈️"),
}

def _wmo(code):
    d, ic = WMO_MAP.get(int(code), ("날씨","🌡️"))
    return d, ic

def update_jp_weather():
    cfg = _read_json(JPWX_CFG, {"enabled": True, "ui": {"interval": 30}})
    if not cfg.get("enabled", True):
        return

    # panels.json에서 enabled 상태를 읽어서 보존 (사용자가 패널을 닫은 상태 유지)
    panels_data = _read_json(PANELS_PATH, DEFAULT_PANELS)
    last_enabled = panels_data.get("panels", {}).get("jpwx", {}).get("enabled", True)
    
    out_items = []
    for c in JP_CITIES:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={c['lat']}&longitude={c['lon']}"
            "&daily=weathercode,temperature_2m_max,temperature_2m_min"
            "&current_weather=true"
            "&timezone=Asia%2FTokyo"
        )
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            r.raise_for_status()
            data = r.json()

            cur = data.get("current_weather", {}) or {}
            cur_temp = cur.get("temperature")
            cur_code = cur.get("weathercode", 0)
            cur_desc, cur_icon = _wmo(cur_code)

            daily = data.get("daily", {}) or {}
            tmax = daily.get("temperature_2m_max", [])
            tmin = daily.get("temperature_2m_min", [])
            wcode = daily.get("weathercode", [])

            def pack(idx):
                try:
                    desc, ic = _wmo(wcode[idx])
                    return {"min": tmin[idx], "max": tmax[idx], "code": wcode[idx], "desc": desc, "icon": ic}
                except:
                    return {"min": None, "max": None, "code": None, "desc": "", "icon": "🌡️"}

            out_items.append({
                "cityKey": c["key"],
                "city": c["name"],
                "now": {"temp": cur_temp, "desc": cur_desc, "icon": cur_icon},
                "today": pack(0),
                "tomorrow": pack(1),
            })

        except Exception as e:
            out_items.append({"cityKey": c["key"], "city": c["name"], "error": f"{type(e).__name__}"})

    out = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "sourceName": "Open-Meteo (JP Weather)",
        "ui": cfg.get("ui", {"interval": 30}),
        "items": out_items,
        "enabled": last_enabled
    }
    _atomic_write_json(JPWX_PATH, out)

def jp_weather_loop():
    while True:
        update_jp_weather()
        time.sleep(1800)

# --- ICN ---

def update_icn_terminal_view():
    cfg = _read_json(ICN_CFG, {"enabled": True, "ui": {"show": 12, "query": ""}})
    if not cfg.get("enabled", True):
        return

    base = _read_json(ICN_TERM_PATH, {"items": []})
    items = base.get("items", [])
    q = (cfg.get("ui", {}).get("query") or "").strip().lower()
    show = int(cfg.get("ui", {}).get("show", 12))
    
    # panels.json에서 enabled 상태를 읽어서 보존 (사용자가 패널을 닫은 상태 유지)
    panels_data = _read_json(PANELS_PATH, DEFAULT_PANELS)
    last_enabled = panels_data.get("panels", {}).get("icn", {}).get("enabled", True)

    if q:
        def match(it):
            return q in (it.get("airline","").lower()) or q in (it.get("iata","").lower()) or q in (it.get("icao","").lower())
        items = [it for it in items if match(it)]

    out = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "sourceName": base.get("sourceName", "ICN Terminal Guide"),
        "ui": cfg.get("ui", {"show": 12, "query": ""}),
        "items": items[:show],
        "enabled": last_enabled
    }
    _atomic_write_json(ICN_OUT_PATH, out)

def icn_loop():
    while True:
        update_icn_terminal_view()
        time.sleep(10)


# =========================================================
# 최초 기본 JSON 생성 (AppData)
# =========================================================
def _copy_if_missing(dst_path: str, src_path: Path):
    if (not os.path.exists(dst_path)) and src_path.exists():
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(src_path, "rb") as fsrc:
            data = fsrc.read()
        with open(dst_path, "wb") as fdst:
            fdst.write(data)

def ensure_default_files():
    # overlay 데이터 폴더는 이미 생성됨
    def ensure(path: str, default_obj):
        if not os.path.exists(path):
            _atomic_write_json(path, default_obj)

    ensure(THEME_PATH, {})
    ensure(BREAKING_PATH, {"text": ""})
    ensure(BANNER_PATH, {"text": ""})
    ensure(NEWS_PATH, {"updated": "", "items": []})
    ensure(STOCK_PATH, {"updated": "", "domestic": {}, "global": {}})
    ensure(SOOP_TOP_PATH, {"updated": "", "items": []})
    ensure(LAYOUT_PATH, {"mode": 1, "items": [{"src": ""}, {"src": ""}, {"src": ""}, {"src": ""}]})
    ensure(LIVE_PATH, {"enabled": True, "mode": "live", "text": "생방송중 Live!"})
    ensure(ROOKIE_PATH, {"updated": "", "items": []})
    ensure(UI_PATH, {"floatingMenu": {"hidden": False}})
    ensure(JOBS_JP_PATH, {"updated": "", "items": []})
    ensure(JOBS_JP_CFG, DEFAULT_JOBS_CFG)
    ensure(JPWX_CFG, {"enabled": True, "ui": {"interval": 30}})
    ensure(ICN_CFG, {"enabled": True, "ui": {"show": 12, "query": ""}})
    ensure(PANELS_PATH, DEFAULT_PANELS)
    ensure(BACKGROUND_ROTATION_PATH, {"enabled": False, "interval_minutes": 15})

# ✅ ICN 입력 데이터: 설치폴더 overlay에 있으면 AppData로 초기 복사
_copy_if_missing(ICN_TERM_PATH, OVERLAY_STATIC_DIR / "icn_terminals.json")

# =========================================================
# 백그라운드 작업 시작 (런처에서 호출)
# =========================================================
_BG_STARTED = False
_BG_LOCK = threading.Lock()

def start_background_jobs(app: Flask, data_root: Path | None = None) -> None:
    """
    app_main.py가 서버 실행 전에 호출.
    이 함수가 1회만 실행되도록 보호.
    """
    global _BG_STARTED
    with _BG_LOCK:
        if _BG_STARTED:
            return
        _BG_STARTED = True

    ensure_default_files()

    # metrics sampler
    threading.Thread(target=metrics_loop, daemon=True).start()

    # 각종 loop
    threading.Thread(target=stock_loop, daemon=True).start()
    threading.Thread(target=news_loop, daemon=True).start()
    threading.Thread(target=soop_top_loop, daemon=True).start()
    threading.Thread(target=rookie_loop, daemon=True).start()
    threading.Thread(target=jobs_jp_loop, daemon=True).start()
    threading.Thread(target=jp_weather_loop, daemon=True).start()
    threading.Thread(target=icn_loop, daemon=True).start()
    threading.Thread(target=background_rotation_loop, daemon=True).start()

# =========================================================
# (개발용) 단독 실행 시 동작 - 설치형에서는 app_main.py 사용 권장
# =========================================================
if __name__ == "__main__":
    app = create_app()
    start_background_jobs(app)
    app.run(host="127.0.0.1", port=8080, debug=True)

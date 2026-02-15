from flask import Flask, request, jsonify, send_from_directory
import json, threading, os, time, re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import xml.etree.ElementTree as ET
import psutil
import time


# --- 주식 ---
import yfinance as yf
import pytz

# --- 뉴스 RSS ---c
import feedparser

import requests
import re

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOOP_CLIENT_ID = os.environ.get("SOOP_CLIENT_ID", "").strip()
SOOP_TOP_PATH = os.path.join(BASE_DIR, "overlay", "soop_top.json")

# =========================
# 파일 경로
# =========================
THEME_PATH    = os.path.join(BASE_DIR, "overlay", "theme.json")
BREAKING_PATH = os.path.join(BASE_DIR, "overlay", "breaking.json")
BANNER_PATH   = os.path.join(BASE_DIR, "overlay", "banner.json")
STOCK_PATH    = os.path.join(BASE_DIR, "overlay", "stock.json")
NEWS_PATH     = os.path.join(BASE_DIR, "overlay", "news.json")
LAYOUT_PATH = os.path.join(BASE_DIR, "overlay", "layout.json")
LIVE_PATH = os.path.join(BASE_DIR, "overlay", "live.json")
ROOKIE_PATH = os.path.join(BASE_DIR, "overlay", "rookie.json")
UI_PATH = os.path.join(BASE_DIR, "overlay", "ui.json")
JOBS_JP_PATH = os.path.join(BASE_DIR, "overlay", "jobs_jp.json")
JOBS_JP_CFG  = os.path.join(BASE_DIR, "overlay", "jobs_jp_config.json")

KST = pytz.timezone("Asia/Seoul")

# =========================
# System Metrics Sampler
# =========================
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
    # Windows는 C:\가 안전, Linux/mac은 /
    try:
        if os.name == "nt":
            return psutil.disk_usage("C:\\").percent
        return psutil.disk_usage("/").percent
    except:
        return None

def metrics_loop():
    # cpu_percent는 "이전 호출 이후"를 기준으로 계산되므로, 0 방지를 위해 한 번 워밍업
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)

    # 프로세스 cpu_percent도 워밍업
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

        # TOP 프로세스 (CPU/메모리)
        procs = []
        for p in psutil.process_iter(attrs=["pid", "name"]):
            try:
                cpu_p = p.cpu_percent(interval=None)  # 샘플러 주기(1초) 기준
                mem_mb = (p.memory_info().rss / (1024 * 1024))
                if cpu_p > 0.0 or mem_mb > 50:  # 너무 자잘한 건 제외(선택)
                    procs.append({
                        "pid": p.info.get("pid"),
                        "name": p.info.get("name") or "unknown",
                        "cpu": round(cpu_p, 1),
                        "mem_mb": round(mem_mb, 1)
                    })
            except:
                continue

        # CPU 상위 5개 우선, 그다음 MEM 상위 섞기(간단히 CPU 기준 정렬)
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

# 샘플러 스레드 시작 (앱 시작 시 1회)
threading.Thread(target=metrics_loop, daemon=True).start()

# =========================
# 정적 파일 라우팅
# =========================
@app.route("/")
def root():
    return send_from_directory(BASE_DIR, "overlay/index.html")

@app.route("/overlay/<path:path>")
def overlay_files(path):
    return send_from_directory("overlay", path)

@app.route("/admin/<path:path>")
def admin_files(path):
    return send_from_directory("admin", path)

# =========================
# 재난 속보 API
# =========================
@app.route("/api/breaking", methods=["POST"])
def breaking():
    data = request.json or {}
    text = data.get("text", "")
    expire = data.get("expire", 0)

    with open(BREAKING_PATH, "w", encoding="utf-8") as f:
        json.dump({"text": text}, f, ensure_ascii=False, indent=2)

    if expire and expire > 0:
        threading.Timer(expire * 60, clear_breaking).start()

    return jsonify(ok=True)

@app.route("/api/clear", methods=["POST"])
def clear_breaking():
    with open(BREAKING_PATH, "w", encoding="utf-8") as f:
        json.dump({"text": ""}, f, ensure_ascii=False, indent=2)
    return jsonify(ok=True)

# =========================
# 배너 API
# =========================
@app.route("/api/banner", methods=["POST"])
def banner():
    data = request.json or {}
    text = data.get("text", "")
    expire = data.get("expire", 0)

    with open(BANNER_PATH, "w", encoding="utf-8") as f:
        json.dump({"text": text}, f, ensure_ascii=False, indent=2)

    if expire and expire > 0:
        threading.Timer(expire * 60, clear_banner).start()

    return jsonify(ok=True)

@app.route("/api/banner/clear", methods=["POST"])
def clear_banner():
    with open(BANNER_PATH, "w", encoding="utf-8") as f:
        json.dump({"text": ""}, f, ensure_ascii=False, indent=2)
    return jsonify(ok=True)

# =========================
# 배경 API
# =========================
@app.route("/api/theme", methods=["POST"])
def theme_set():
    data = request.json or {}

    # { "--panel-bg": "...", "--lower-bg": "..."} 형태로 저장
    with open(THEME_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return jsonify(ok=True)

@app.route("/api/theme/clear", methods=["POST"])
def theme_clear():
    # 빈 객체면 오버레이는 기본 CSS(:root) 값 사용
    with open(THEME_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)
    return jsonify(ok=True)


# =========================
# 주식 자동 갱신 (Yahoo Finance)
# =========================
SYMBOLS = {
    "domestic": {
        "KOSPI": "^KS11",
        "KOSDAQ": "^KQ11"
    },
    "global": {
        "NASDAQ": "^IXIC",
        "DOW": "^DJI",
        "S&P500": "^GSPC"
    }
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

    with open(STOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("[STOCK UPDATED]", result["updated"])

def stock_loop():
    while True:
        update_stock()
        time.sleep(300)  # 5분

# =========================
# 뉴스 자동 갱신 (RSS → news.json)
# =========================
RSS_URL = "https://www.yna.co.kr/rss/news.xml"
MAX_NEWS_ITEMS = 5

def clean_title(title: str) -> str:
    remove_words = [
        "종합", "속보", "단독", "포토", "영상",
        "[속보]", "[단독]", "(종합)"
    ]
    for word in remove_words:
        title = title.replace(word, "")
    return title.strip()

def update_news():
    try:
        feed = feedparser.parse(RSS_URL)

        items = []
        for entry in feed.entries[:MAX_NEWS_ITEMS]:
            items.append(clean_title(entry.title))

        output = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "items": items
        }

        with open(NEWS_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"[NEWS UPDATED] {output['updated']} ({len(items)}건)")
    except Exception as e:
        print("[NEWS ERROR]", e)

def news_loop():
    while True:
        update_news()
        time.sleep(300)  # 5분마다 갱신 (원하면 60~300초 조정 가능)

# =========================
# soop top10 자동 갱신
# =========================
def _write_soop_top_empty(reason="disabled"):
    out = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "items": [],
        "disabled": True,
        "reason": reason
    }
    with open(SOOP_TOP_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def _parse_jsonp(text: str):
    # cb({...}) → {...}
    m = re.search(r'^[a-zA-Z0-9_]+\((.*)\)\s*;?\s*$', text.strip(), re.DOTALL)
    return json.loads(m.group(1)) if m else json.loads(text)

def update_soop_top():
    # 1) client_id 없으면 기능 OFF
    if not SOOP_CLIENT_ID:
        _write_soop_top_empty("missing_client_id")
        return

    url = "https://openapi.sooplive.co.kr/broad/list"
    params = {
        "client_id": SOOP_CLIENT_ID,
        "order_type": "view_cnt",
        "page_no": 1,
        "callback": "cb"
    }

    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        payload = _parse_jsonp(r.text)

        # result 체크 (성공이 아닐 때도 OFF 처리)
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
        with open(SOOP_TOP_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    except Exception as e:
        _write_soop_top_empty(f"exception:{type(e).__name__}")

def soop_top_loop():
    while True:
        update_soop_top()
        time.sleep(60)

# =========================
# 화면 레이아웃 API
# =========================
@app.route("/api/layout", methods=["POST"])
def layout_set():
    data = request.json or {}
    # 최소 방어
    mode = int(data.get("mode", 1))
    if mode not in (1, 2, 4):
        mode = 1

    items = data.get("items", [])
    if not isinstance(items, list):
        items = []

    # 4개로 고정
    fixed = []
    for i in range(4):
        src = ""
        if i < len(items) and isinstance(items[i], dict):
          src = str(items[i].get("src", "")).strip()
        fixed.append({"src": src})

    out = {"mode": mode, "items": fixed}

    with open(LAYOUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    return jsonify(ok=True)

@app.route("/api/layout/clear", methods=["POST"])
def layout_clear():
    out = {"mode": 1, "items": [{"src": ""}, {"src": ""}, {"src": ""}, {"src": ""}]}
    with open(LAYOUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return jsonify(ok=True)

# =========================
# 라이브 방송 화면 API
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
    with open(LIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    return jsonify(ok=True)

# =========================
# 신규 스트리머 정보 갖고 오는 API
# =========================
ROOKIE_API_URL = "https://afevent2.sooplive.co.kr/app/rank/api.php"

def update_rookie():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://afevent2.sooplive.co.kr",
            "Referer": "https://afevent2.sooplive.co.kr/app/rank/index.php?szWhich=rookie",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

        payload = {
            "szWhich": "rookie",
            "nPage": "1",
            "szSearch": "",
            "szGender": "A",
        }

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
            with open(ROOKIE_PATH, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            return

        items = []
        for it in arr[:10]:
            bj_id = str(it.get("bj_id", "")).strip()
            bj_nick = str(it.get("bj_nick", "")).strip()
            station_title = str(it.get("station_title", "")).strip()
            is_broad = bool(it.get("is_broad", False))

            # 현재 순위/지난 순위
            try:
                rank_now = int(it.get("total_rank") or 0)
            except:
                rank_now = 0
            try:
                rank_last = int(it.get("total_rank_last") or 0)
            except:
                rank_last = 0

            # 변동 계산: last(이전) - now(현재) => +면 상승
            move = "same"
            delta = None
            if rank_now > 0 and rank_last > 0:
                diff = rank_last - rank_now
                if diff > 0:
                    move = "up"
                    delta = diff
                elif diff < 0:
                    move = "down"
                    delta = abs(diff)
            elif rank_now > 0 and rank_last == 0:
                move = "new"
                delta = None

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

        out = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "items": items
        }

        with open(ROOKIE_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        print("[ROOKIE UPDATED]", out["updated"], "items:", len(items))

    except Exception as e:
        out = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "items": [],
            "disabled": True,
            "reason": f"exception:{type(e).__name__}"
        }
        with open(ROOKIE_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

def rookie_loop():
    while True:
        update_rookie()
        time.sleep(300)  # 5분마다 갱신            

# =========================
# UI 정보 갖고 오는 API
# =========================
@app.route("/api/ui/floating/show", methods=["POST"])
def ui_floating_show():
    # ui.json 읽고 hidden=false로 저장
    data = {"floatingMenu": {"hidden": False}}
    try:
        if os.path.exists(UI_PATH):
            with open(UI_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
    except:
        data = {"floatingMenu": {"hidden": False}}

    if "floatingMenu" not in data:
        data["floatingMenu"] = {}
    data["floatingMenu"]["hidden"] = False

    with open(UI_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return jsonify(ok=True)

@app.route("/api/ui/floating/hide", methods=["POST"])
def ui_floating_hide():
    data = {"floatingMenu": {"hidden": True}}
    try:
        if os.path.exists(UI_PATH):
            with open(UI_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
    except:
        data = {"floatingMenu": {"hidden": True}}

    if "floatingMenu" not in data:
        data["floatingMenu"] = {}
    data["floatingMenu"]["hidden"] = True

    with open(UI_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return jsonify(ok=True)

# =========================
# 취업정보 정보 갖고 오는 API
# =========================
INDEED_RSS = "https://rss.indeed.com/rss?q=Japan+software+engineer&l=Japan"

INDEED_PRESETS = {
    # key: {name, q, l}
    "jp_se_tokyo":   {"name": "🇯🇵 Tokyo - Software Engineer", "q": "software engineer", "l": "Tokyo"},
    "jp_se_all":     {"name": "🇯🇵 Japan - Software Engineer", "q": "software engineer", "l": "Japan"},
    "jp_backend":    {"name": "🇯🇵 Backend Engineer",          "q": "backend engineer",  "l": "Japan"},
    "jp_frontend":   {"name": "🇯🇵 Frontend Engineer",         "q": "frontend engineer", "l": "Japan"},
    "jp_data":       {"name": "🇯🇵 Data Engineer",             "q": "data engineer",     "l": "Japan"},
    "jp_pm":         {"name": "🇯🇵 Product Manager",           "q": "product manager",   "l": "Japan"},
    "jp_english":    {"name": "🇯🇵 English OK (keyword)",       "q": "software engineer english", "l": "Japan"},
}
DEFAULT_PRESET_KEY = "jp_se_tokyo"

'''
def update_jobs_jp():
    try:
        r = requests.get(INDEED_RSS, timeout=12)
        r.raise_for_status()

        root = ET.fromstring(r.text)
        channel = root.find("channel")
        items = []
        if channel is not None:
            for item in channel.findall("item")[:10]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                items.append({"title": title, "link": link, "pubDate": pub})

        out = {"updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "items": items}
        with open(JOBS_JP_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    except Exception as e:
        # 실패 시 기존 유지(방송 안정)하거나 비우기 선택
        out = {"updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "items": [], "disabled": True, "reason": type(e).__name__}
        with open(JOBS_JP_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
'''
def jobs_jp_loop():
    while True:
        update_jobs_jp()
        time.sleep(600)

def build_indeed_rss_url(q: str, l: str) -> str:
    # Indeed RSS는 q/l 쿼리를 URL 인코딩해서 붙이면 됩니다.
    # 예: https://rss.indeed.com/rss?q=software+engineer&l=Tokyo
    import urllib.parse
    qs = urllib.parse.urlencode({"q": q, "l": l})
    return f"https://rss.indeed.com/rss?{qs}"

'''
def load_jobs_cfg():
    try:
        with open(JOBS_JP_CFG, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        preset = cfg.get("preset", DEFAULT_PRESET_KEY)
        if preset not in INDEED_PRESETS:
            preset = DEFAULT_PRESET_KEY
        return preset
    except:
        return DEFAULT_PRESET_KEY
'''
def load_jobs_cfg_full():
    cfg = {
        "preset": DEFAULT_PRESET_KEY,
        "custom": {"q": "software engineer", "l": "Japan"},
        "ui": {"count": 6, "roll": True, "interval": 10}
    }
    try:
        if os.path.exists(JOBS_JP_CFG):
            with open(JOBS_JP_CFG, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg.update(loaded)
    except:
        pass

    # sanitize
    if cfg.get("preset") not in INDEED_PRESETS and cfg.get("preset") != "custom":
        cfg["preset"] = DEFAULT_PRESET_KEY

    if not isinstance(cfg.get("custom"), dict):
        cfg["custom"] = {"q": "software engineer", "l": "Japan"}

    ui = cfg.get("ui") if isinstance(cfg.get("ui"), dict) else {}
    count = ui.get("count", 6)
    roll = ui.get("roll", True)
    interval = ui.get("interval", 10)

    try:
        count = int(count)
    except:
        count = 6
    count = max(1, min(10, count))

    roll = bool(roll)
    try:
        interval = int(interval)
    except:
        interval = 10
    interval = max(3, min(60, interval))

    cfg["ui"] = {"count": count, "roll": roll, "interval": interval}

    q = str(cfg["custom"].get("q", "software engineer")).strip()[:120]
    l = str(cfg["custom"].get("l", "Japan")).strip()[:80]
    cfg["custom"] = {"q": q, "l": l}

    return cfg

def update_jobs_jp():
    cfg = load_jobs_cfg_full()
    preset_key = cfg.get("preset", DEFAULT_PRESET_KEY)

    if preset_key == "custom":
        q = cfg["custom"]["q"]
        l = cfg["custom"]["l"]
        preset_name = f"🛠 커스텀: {q} / {l}"
    else:
        preset = INDEED_PRESETS.get(preset_key, INDEED_PRESETS[DEFAULT_PRESET_KEY])
        q = preset["q"]
        l = preset["l"]
        preset_name = preset["name"]

    rss_url = build_indeed_rss_url(q, l)

    try:
        r = requests.get(rss_url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()

        root = ET.fromstring(r.text)
        channel = root.find("channel")
        items = []

        if channel is not None:
            for item in channel.findall("item")[:30]:  # 롤링을 위해 넉넉히 받아둠
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub  = (item.findtext("pubDate") or "").strip()
                if title:
                    items.append({"title": title, "link": link, "pubDate": pub})

        out = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "preset": preset_key,
            "presetName": preset_name,
            "ui": cfg["ui"],                # ✅ UI 옵션을 overlay로 전달
            "items": items
        }

        with open(JOBS_JP_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        print("[JOBS_JP UPDATED]", out["updated"], preset_key, "items:", len(items))

    except Exception as e:
        out = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "preset": preset_key,
            "presetName": preset_name,
            "ui": cfg["ui"],
            "items": [],
            "disabled": True,
            "reason": f"exception:{type(e).__name__}"
        }
        with open(JOBS_JP_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

@app.route("/api/jobsjp/presets", methods=["GET"])
def jobsjp_presets():
    cfg = load_jobs_cfg_full()
    presets = [{"key": k, **v} for k, v in INDEED_PRESETS.items()]
    presets.insert(0, {"key": "custom", "name": "🛠 커스텀 (q/l 직접입력)", "q": "", "l": ""})
    return jsonify(ok=True, presets=presets, current=cfg)

@app.route("/api/jobsjp/config", methods=["POST"])
def jobsjp_config():
    req = request.json or {}
    cfg = load_jobs_cfg_full()

    preset = req.get("preset", cfg["preset"])
    if preset != "custom" and preset not in INDEED_PRESETS:
        preset = DEFAULT_PRESET_KEY
    cfg["preset"] = preset

    custom = req.get("custom")
    if isinstance(custom, dict):
        q = str(custom.get("q", cfg["custom"]["q"])).strip()[:120]
        l = str(custom.get("l", cfg["custom"]["l"])).strip()[:80]
        cfg["custom"] = {"q": q, "l": l}

    ui = req.get("ui")
    if isinstance(ui, dict):
        try:
            cfg["ui"]["count"] = max(1, min(10, int(ui.get("count", cfg["ui"]["count"]))))
        except:
            pass
        cfg["ui"]["roll"] = bool(ui.get("roll", cfg["ui"]["roll"]))
        try:
            cfg["ui"]["interval"] = max(3, min(60, int(ui.get("interval", cfg["ui"]["interval"]))))
        except:
            pass

    with open(JOBS_JP_CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    update_jobs_jp()
    return jsonify(ok=True, current=cfg)


# =========================
# 자원 정보 갖고 오는 API
# =========================
@app.route("/api/metrics", methods=["GET"])
def metrics():
    with _metrics_lock:
        return jsonify(METRICS_CACHE)


# =========================
# 최초 파일이 없으면 기본값 생성
# =========================
def ensure_default_files():
    os.makedirs(os.path.join(BASE_DIR, "overlay"), exist_ok=True)

    if not os.path.exists(THEME_PATH):
        with open(THEME_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
            
    if not os.path.exists(BREAKING_PATH):
        with open(BREAKING_PATH, "w", encoding="utf-8") as f:
            json.dump({"text": ""}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(BANNER_PATH):
        with open(BANNER_PATH, "w", encoding="utf-8") as f:
            json.dump({"text": ""}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(NEWS_PATH):
        with open(NEWS_PATH, "w", encoding="utf-8") as f:
            json.dump({"updated": "", "items": []}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(STOCK_PATH):
        with open(STOCK_PATH, "w", encoding="utf-8") as f:
            json.dump({"updated": "", "domestic": {}, "global": {}}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(SOOP_TOP_PATH):
        with open(SOOP_TOP_PATH, "w", encoding="utf-8") as f:
            json.dump({"updated": "", "items": []}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(LAYOUT_PATH):
        with open(LAYOUT_PATH, "w", encoding="utf-8") as f:
            json.dump({"mode": 1, "items": [{"src": ""}, {"src": ""}, {"src": ""}, {"src": ""}]}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(LIVE_PATH):
        with open(LIVE_PATH, "w", encoding="utf-8") as f:
            json.dump({"enabled": True, "mode": "live", "text": "생방송중 Live!"}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(ROOKIE_PATH):
        with open(ROOKIE_PATH, "w", encoding="utf-8") as f:
            json.dump({"updated": "", "items": []}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(UI_PATH):
        with open(UI_PATH, "w", encoding="utf-8") as f:
            json.dump({"floatingMenu": {"hidden": False}}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(JOBS_JP_PATH):
        with open(JOBS_JP_PATH, "w", encoding="utf-8") as f:
            json.dump({"updated": "", "items": []}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(JOBS_JP_CFG):
        with open(JOBS_JP_CFG, "w", encoding="utf-8") as f:
            json.dump({
                "preset": DEFAULT_PRESET_KEY,
                "custom": {"q": "software engineer", "l": "Japan"},
                "ui": {"count": 6, "roll": True, "interval": 10}
            }, f, ensure_ascii=False, indent=2)



# =========================
# 실행
# =========================
if __name__ == "__main__":
    ensure_default_files()

    # 백그라운드 자동 갱신 스레드 시작
    threading.Thread(target=stock_loop, daemon=True).start()
    threading.Thread(target=news_loop, daemon=True).start()
    threading.Thread(target=soop_top_loop, daemon=True).start()
    threading.Thread(target=rookie_loop, daemon=True).start()
    threading.Thread(target=jobs_jp_loop, daemon=True).start()

    app.run(port=8080, debug=True)

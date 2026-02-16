from flask import Flask, request, jsonify, send_from_directory
import json, threading, os, time, re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
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
JOBS_JP_PATH = os.path.join(BASE_DIR, "overlay", "jobs_jp.json")
JOBS_JP_CFG  = os.path.join(BASE_DIR, "overlay", "jobs_jp_config.json")
PANELS_PATH = os.path.join(BASE_DIR, "overlay", "panels.json")

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
      "jd_all":        {"name": "🇯🇵 Japan Dev - 전체",          "url": "https://japan-dev.com/jobs"},
      "jd_tokyo":      {"name": "🇯🇵 Japan Dev - 도쿄",          "url": "https://japan-dev.com/jobs-in-tokyo"},
      "jd_relocation": {"name": "🇯🇵 Japan Dev - 비자/리로케이션", "url": "https://japan-dev.com/japan-jobs-relocation"},
    }
  }
}

'''
DEFAULT_PANELS = {
  "updated": "",
  "panels": {
    "jobsjp": {"enabled": True, "width": 360, "opacity": 0.22, "fontSize": 13},
    "jpwx":   {"enabled": True, "width": 360, "opacity": 0.22, "fontSize": 13},
    "icn":    {"enabled": True, "width": 360, "opacity": 0.22, "fontSize": 13}
  }
}
'''

DEFAULT_PANELS = {
  "updated": "",
  "resetToken": 0,
  "panels": { ... }
}
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
JPWX_PATH = os.path.join(BASE_DIR, "overlay", "jp_weather.json")
ICN_TERM_PATH = os.path.join(BASE_DIR, "overlay", "icn_terminals.json")
JPWX_CFG = os.path.join(BASE_DIR, "overlay", "jp_weather_config.json")
ICN_CFG  = os.path.join(BASE_DIR, "overlay", "icn_config.json")


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
WORK24_API_KEY = os.getenv("WORK24_API_KEY", "")
WORK24_LIST_URL = "https://www.work24.go.kr/openapi/service/..."  # 문서의 요청 URL로 교체

def fetch_work24_jobs(limit=30):
    if not WORK24_API_KEY:
        raise Exception("WORK24_API_KEY missing")

    params = {
        "serviceKey": WORK24_API_KEY,
        "callTp": "L",
        "returnType": "xml",
        "startPage": 1,
        "display": min(100, limit),
        # 해외 관련 필터는 Work24가 제공하는 region/occupation 등 코드로 매핑
        # "region": "...",
        # "occupation": "...",
    }

    r = requests.get(WORK24_LIST_URL, params=params, timeout=12)
    r.raise_for_status()

    # XML 파싱해서 title/link/pubDate 형태로 변환
    root = ET.fromstring(r.text)
    items = []
    for it in root.findall(".//item")[:limit]:
        title = (it.findtext("recrutPblntSn") or it.findtext("title") or "").strip()
        # Work24는 상세로 가는 키/링크 패턴이 있을 수 있어 조합 필요
        link = ""
        pub = (it.findtext("regDt") or "").strip()
        if title:
            items.append({"title": title, "link": link, "pubDate": pub})
    return items




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
        time.sleep(1800)  # 30분

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
    with open(JOBS_JP_CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default
    
def fetch_tokyodev(url, limit=30):
    r = requests.get(url, timeout=12, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    })
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    items = []
    seen = set()

    # TokyoDev는 /jobs 경로에서 목록이 바로 노출됨 :contentReference[oaicite:2]{index=2}
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)

        if not href or not text:
            continue

        # 상세/목록 링크가 /jobs 로 시작하는 패턴 중심으로
        if "/jobs" not in href:
            continue

        full = urljoin("https://www.tokyodev.com", href)
        key = (text, full)
        if key in seen:
            continue

        # 너무 긴 본문/메뉴 텍스트 제거(대충 필터)
        if len(text) < 8 or len(text) > 140:
            continue

        seen.add(key)
        items.append({"title": text, "link": full, "pubDate": ""})
        if len(items) >= limit:
            break

    return items

def fetch_japandev(url, limit=30):
    r = requests.get(url, timeout=12, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    })
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    items = []
    seen = set()

    # Japan Dev는 /jobs, /jobs-in-tokyo 등 목록 페이지 제공 :contentReference[oaicite:3]{index=3}
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)

        if not href or not text:
            continue

        # job 상세가 /jobs 로 시작하는 링크가 많음(구조 변경 대비 넓게)
        if "/jobs" not in href:
            continue

        full = urljoin("https://japan-dev.com", href)
        key = (text, full)
        if key in seen:
            continue

        if len(text) < 8 or len(text) > 160:
            continue

        seen.add(key)
        items.append({"title": text, "link": full, "pubDate": ""})
        if len(items) >= limit:
            break

    return items


'''
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

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    }

    # 마지막 성공 데이터 읽기(실패 시 유지용)
    last = _read_json(JOBS_JP_PATH, {"updated": "", "items": []})
    last_items = last.get("items") if isinstance(last, dict) else []
    if not isinstance(last_items, list):
        last_items = []

    try:
        r = requests.get(rss_url, timeout=12, headers=headers)

        # 429/403 등 차단 시: 기존 items 유지
        if r.status_code != 200:
            # 429면 특히 "그냥 유지"가 방송 안정
            out = {
                "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "preset": preset_key,
                "presetName": preset_name,
                "ui": cfg["ui"],
                "items": last_items,  # ✅ 유지
                "disabled": False,    # ✅ 화면은 계속 보여주기
                "warn": f"http_status:{r.status_code}",
                "debug": {
                    "url": rss_url,
                    "content_type": r.headers.get("Content-Type", ""),
                    "body_head": (r.text or "")[:120]
                }
            }
            with open(JOBS_JP_PATH, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            return

        # 정상 RSS 파싱
        root = ET.fromstring(r.text)
        channel = root.find("channel")
        items = []
        if channel is not None:
            for item in channel.findall("item")[:30]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                if title:
                    items.append({"title": title, "link": link, "pubDate": pub})

        out = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "preset": preset_key,
            "presetName": preset_name,
            "ui": cfg["ui"],
            "items": items
        }
        with open(JOBS_JP_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    except Exception as e:
        # 예외도 동일하게 last 유지
        out = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "preset": preset_key,
            "presetName": preset_name,
            "ui": cfg["ui"],
            "items": last_items,
            "disabled": False,
            "warn": f"exception:{type(e).__name__}",
            "debug": {"url": rss_url}
        }
        with open(JOBS_JP_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    '''
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
                "items": items
            }

        with open(JOBS_JP_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        print("[JOBS UPDATED]", out["updated"], preset_key, "items:", len(out["items"]))

    except Exception as e:
        out = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "preset": preset_key,
            "presetName": preset_name,
            "sourceName": JOB_SOURCES[source]["name"],
            "ui": cfg["ui"],
            "items": last_items,
            "disabled": False,
            "warn": f"exception:{type(e).__name__}",
            "debug": {"url": url}
        }
        with open(JOBS_JP_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

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
# 자원 정보 갖고 오는 API
# =========================
@app.route("/api/metrics", methods=["GET"])
def metrics():
    with _metrics_lock:
        return jsonify(METRICS_CACHE)
# =========================
# 함수
# =========================
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
    # ¥10.0m ~ ¥15m / ¥8m / $120k 등 대략 추정
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
    # 카드 안에서 회사명 후보를 최대한 찾기 (완벽하진 않음)
    # 1) data-company 같은 속성이 있으면 사용
    try:
        for attr in ["data-company", "data-employer", "data-company-name"]:
            v = card.get(attr)
            if v and len(v) <= 60:
                return _clean(v)
    except:
        pass

    # 2) card 안에서 "Company" / "Employer" 스타일 label을 찾는 방식(사이트마다 다름)
    # 3) fallback: "at XXX" 패턴
    m = re.search(r"\bat\s+([A-Za-z0-9\-\&\.\s]{2,40})", fallback_text or "")
    if m:
        return _clean(m.group(1))

    return ""


def _extract_location(card_text: str) -> str:
    t = (card_text or "").lower()
    # 대략적인 키워드 탐지 (Tokyo/Remote 등)
    if "remote" in t:
        return "Remote"
    if "tokyo" in t:
        return "Tokyo"
    if "osaka" in t:
        return "Osaka"
    if "japan" in t:
        return "Japan"
    return ""


def _collect_tags(card) -> list:
    tags = []
    if not card:
        return tags
    # 너무 공격적으로 긁으면 메뉴/네비까지 들어오니 짧은 텍스트만 태그로
    for node in card.select("span, li, div"):
        txt = _clean(node.get_text(" ", strip=True))
        if 2 <= len(txt) <= 28 and txt not in tags:
            # 흔한 잡텍스트 제외
            low = txt.lower()
            if low in ["apply", "learn more", "view", "jobs", "job"]:
                continue
            tags.append(txt)
        if len(tags) >= 10:
            break
    return tags


def fetch_tokyodev_struct(url: str, limit: int = 30) -> list:
    r = requests.get(url, timeout=12, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    })
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    items, seen = [], set()

    # ✅ 1) 상세 링크만: /jobs/<slug> 형태만 통과 (필터 강화)
    for a in soup.select('a[href^="/jobs/"]'):
        href = a.get("href", "")
        # /jobs/ 뒤에 뭔가가 있어야 함
        if href.count("/") < 2:
            continue
        # 목록/카테고리 링크 제외 (예: /jobs/backend 같은 경우)
        if href in ["/jobs/backend", "/jobs/frontend", "/jobs"]:
            continue

        link = urljoin("https://www.tokyodev.com", href)

        # ✅ 2) 제목은 h2/h3 우선
        h = a.select_one("h2,h3")
        title = _clean(h.get_text(" ", strip=True)) if h else _clean(a.get_text(" ", strip=True))
        if not title or len(title) < 10:
            continue

        # ✅ 3) 카드(공고) 단위 확실히 잡기: article 우선
        card = a.find_parent("article") or a.find_parent(["li","div"])
        if not card:
            continue

        # 카드 전체 텍스트
        card_text = _clean(card.get_text(" ", strip=True))

        # ✅ 태그/칩만 따로 수집 (전체 텍스트에서 마구 긁지 않기)
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
    r = requests.get(url, timeout=12, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    })
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

# =========================
# 도쿄/오사카/후쿠오카 날씨 정보 갖고 오는 API
# =========================
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

            # today index 0, tomorrow index 1
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
            out_items.append({
                "cityKey": c["key"], "city": c["name"],
                "error": f"{type(e).__name__}"
            })

    out = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "sourceName": "Open-Meteo (JP Weather)",
        "ui": cfg.get("ui", {"interval": 30}),
        "items": out_items
    }

    with open(JPWX_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def jp_weather_loop():
    while True:
        update_jp_weather()
        time.sleep(1800)  # 30분        

# =========================
# ICN 터미널 안내 API

ICN_OUT_PATH = os.path.join(BASE_DIR, "overlay", "icn_terminal_view.json")

def update_icn_terminal_view():
    cfg = _read_json(ICN_CFG, {"enabled": True, "ui": {"show": 12, "query": ""}})
    if not cfg.get("enabled", True):
        return

    base = _read_json(ICN_TERM_PATH, {"items": []})
    items = base.get("items", [])
    q = (cfg.get("ui", {}).get("query") or "").strip().lower()
    show = int(cfg.get("ui", {}).get("show", 12))

    if q:
        def match(it):
            return q in (it.get("airline","").lower()) or q in (it.get("iata","").lower()) or q in (it.get("icao","").lower())
        items = [it for it in items if match(it)]

    out = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "sourceName": base.get("sourceName", "ICN Terminal Guide"),
        "ui": cfg.get("ui", {"show": 12, "query": ""}),
        "items": items[:show]
    }
    with open(ICN_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def icn_loop():
    while True:
        update_icn_terminal_view()
        time.sleep(10)  # 검색 반영 빠르게

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

    with open(ICN_CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    update_icn_terminal_view()
    return jsonify(ok=True, current=cfg)

# =========================
# 패널 설정 API
# =========================
@app.route("/api/panels", methods=["GET"])
def get_panels():
    data = _read_json(PANELS_PATH, DEFAULT_PANELS)
    return jsonify(ok=True, data=data)

# 패널 설정 저장 API: 클라이언트에서 패널별 설정을 받아서 저장 (너무 공격적으로 업데이트하지 않도록 주의)
@app.route("/api/panels", methods=["POST"])
def save_panels():
    req = request.json or {}
    data = _read_json(PANELS_PATH, DEFAULT_PANELS)

    panels = req.get("panels", {})
    if not isinstance(panels, dict):
        panels = {}

    # sanitize
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

    with open(PANELS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return jsonify(ok=True, data=data)

# 패널 리셋 API: 패널 설정을 초기값으로 리셋 (resetToken을 증가시켜 클라이언트에 리셋 신호 전달)
@app.route("/api/panels/reset", methods=["POST"])
def panels_reset():
    data = _read_json(PANELS_PATH, DEFAULT_PANELS)
    data["resetToken"] = int(data.get("resetToken", 0)) + 1
    data["updated"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    with open(PANELS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify(ok=True, resetToken=data["resetToken"])

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
            json.dump(DEFAULT_JOBS_CFG, f, ensure_ascii=False, indent=2)

    if not os.path.exists(JPWX_CFG):
        with open(JPWX_CFG, "w", encoding="utf-8") as f:
            json.dump({"enabled": True, "ui": {"interval": 30}}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(ICN_CFG):
        with open(ICN_CFG, "w", encoding="utf-8") as f:
            json.dump({"enabled": True, "ui": {"show": 12, "query": ""}}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(PANELS_PATH):
        with open(PANELS_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_PANELS, f, ensure_ascii=False, indent=2)

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
    threading.Thread(target=jp_weather_loop, daemon=True).start()

    app.run(port=8080, debug=True)

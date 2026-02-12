from flask import Flask, request, jsonify, send_from_directory
import json, threading, os, time, re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# --- 주식 ---
import yfinance as yf
import pytz

# --- 뉴스 RSS ---
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

KST = pytz.timezone("Asia/Seoul")

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
#ROOKIE_URL = "https://afevent2.sooplive.co.kr/app/rank/index.php?szWhich=rookie"
ROOKIE_URL = "https://afevent2.afreecatv.com/app/rank/index.php?szWhich=rookie"

def update_rookie():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6",
    }

    try:
        r = requests.get(ROOKIE_URL, headers=headers, timeout=12)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True).replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text)

        # ✅ 랭킹 홈의 "신입 스트리머 ... 더보기" 구간
        m = re.search(r"신입\s*스트리머\s*(.*?)\s*더보기", text, re.DOTALL)
        if not m:
            out = {
                "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "items": [],
                "disabled": True,
                "reason": "rookie_section_not_found"
            }
            with open(ROOKIE_PATH, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            return

        block = m.group(1).strip()

        # 예시 텍스트(실제로 이렇게 들어있음):
        # 1 ♡비니♡ up 1 2 구하리♡ down 1 ... 10 해링이 down 7
        item_re = re.compile(
            r"(?<!\d)(10|[1-9])\s+(.+?)\s+(up|down|same|NEW)\s*([0-9]+)?(?=\s+(10|[1-9])\s+|$)",
            re.IGNORECASE
        )

        items = []
        for mm in item_re.finditer(block):
            rank = int(mm.group(1))
            name = mm.group(2).strip()
            move = mm.group(3).lower()
            delta = mm.group(4)
            delta = int(delta) if (delta and delta.isdigit()) else None

            items.append({
                "rank": rank,
                "name": name,
                "move": "new" if move == "new" else move,
                "delta": delta
            })

        items.sort(key=lambda x: x["rank"])
        items = items[:10]

        out = {
            "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "items": items
        }

        # 안전장치: 그래도 비면 block 일부 저장
        if len(items) == 0:
            out["disabled"] = True
            out["reason"] = "parsed_but_empty"
            out["debug"] = block[:220]

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

    app.run(port=8080, debug=True)

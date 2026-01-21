from flask import Flask, request, jsonify, send_from_directory
import json, threading, os, time
from datetime import datetime

# --- 주식 ---
import yfinance as yf
import pytz

# --- 뉴스 RSS ---
import feedparser

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =========================
# 파일 경로
# =========================
THEME_PATH    = os.path.join(BASE_DIR, "overlay", "theme.json")
BREAKING_PATH = os.path.join(BASE_DIR, "overlay", "breaking.json")
BANNER_PATH   = os.path.join(BASE_DIR, "overlay", "banner.json")
STOCK_PATH    = os.path.join(BASE_DIR, "overlay", "stock.json")
NEWS_PATH     = os.path.join(BASE_DIR, "overlay", "news.json")

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

# =========================
# 실행
# =========================
if __name__ == "__main__":
    ensure_default_files()

    # 백그라운드 자동 갱신 스레드 시작
    threading.Thread(target=stock_loop, daemon=True).start()
    threading.Thread(target=news_loop, daemon=True).start()

    app.run(port=8080, debug=True)

import yfinance as yf
import json
import os
from datetime import datetime
import pytz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STOCK_PATH = os.path.join(BASE_DIR, "overlay", "stock.json")

KST = pytz.timezone("Asia/Seoul")

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

def fetch_stock():
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
                prev = info["previous_close"]
                change = round(((price - prev) / prev) * 100, 2)

                result[group][name] = {
                    "price": price,
                    "change": change
                }
            except Exception as e:
                result[group][name] = {
                    "price": None,
                    "change": None
                }

    with open(STOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("[STOCK] updated", result["updated"])

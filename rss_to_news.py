import feedparser
import json
from datetime import datetime

# ===== 설정 =====
RSS_URL = "https://www.yna.co.kr/rss/news.xml"
OUTPUT_FILE = "./overlay/news.json"
MAX_ITEMS = 5

def clean_title(title: str) -> str:
    """
    방송용 문장 정리
    """
    remove_words = [
        "종합", "속보", "단독", "포토", "영상",
        "[속보]", "[단독]", "(종합)"
    ]

    for word in remove_words:
        title = title.replace(word, "")

    return title.strip()

def main():
    feed = feedparser.parse(RSS_URL)

    items = []
    for entry in feed.entries[:MAX_ITEMS]:
        title = clean_title(entry.title)
        items.append(title)

    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "items": items
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[OK] news.json 갱신 ({len(items)}건)")

if __name__ == "__main__":
    main()

import requests, json

url = "https://afevent2.sooplive.co.kr/app/rank/api.php"
headers = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://afevent2.sooplive.co.kr",
    "Referer": "https://afevent2.sooplive.co.kr/app/rank/index.php?szWhich=rookie",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

data = {
    "szWhich": "rookie",
    "nPage": "1",
    "szSearch": "",
    "szGender": "A",
}

r = requests.post(url, headers=headers, data=data, timeout=12)
print("status", r.status_code)
print(r.text[:400])

j = r.json()
print("RESULT", j.get("RESULT"))
print("TOTAL_CNT", j.get("TOTAL_CNT"))
print("ALL_RANK len", len(j.get("ALL_RANK") or []))

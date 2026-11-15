import json
import os
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BOARDS = {
    "주택임대": "https://www.i-sh.co.kr/app/lay2/program/S48T1581C563/www/brd/m_247/list.do",
}

# 제목에 이 글자가 하나라도 있어야 알립니다.
INCLUDE = ["모집"]
# 제목에 이 글자가 있으면 알리지 않습니다.
EXCLUDE = ["발표", "휴무", "당첨", "결과"]

SEEN_FILE = "seen_sh.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def fetch_board(name, url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        num = tds[0].get_text(strip=True)
        if not num.isdigit():
            continue
        title = tds[1].get_text(" ", strip=True)
        date = tds[3].get_text(strip=True)
        a = tds[1].find("a")
        href = a.get("href", "") if a else ""
        if href and not href.startswith(("#", "javascript")):
            link = urljoin(url, href)
        else:
            link = url  # 상세 주소를 못 구하면 목록 페이지로 연결
        items.append({"id": f"{name}:{num}", "title": title, "date": date, "link": link, "board": name})
    if not items:
        raise RuntimeError(f"{name}: 목록을 읽지 못했습니다. 응답 앞부분: {r.text[:300]}")
    return items


def send_telegram(text):
    r = requests.post(
        f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/sendMessage",
        data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text},
        timeout=30,
    )
    r.raise_for_status()


def wanted(title):
    if INCLUDE and not any(k in title for k in INCLUDE):
        return False
    if any(k in title for k in EXCLUDE):
        return False
    return True


def main():
    items = []
    for name, url in BOARDS.items():
        items += fetch_board(name, url)

    first_run = not os.path.exists(SEEN_FILE)
    seen = set()
    if not first_run:
        with open(SEEN_FILE, encoding="utf-8") as f:
            seen = set(json.load(f))

    if first_run:
        send_telegram(f"SH 공고 알림 설정 완료. 기존 글 {len(items)}건은 알리지 않고 기록만 해 두었습니다.")
    else:
        new = [i for i in items if i["id"] not in seen]
        for i in reversed(new):
            if not wanted(i["title"]):
                continue
            send_telegram(f"[SH {i['board']}]\n{i['title']}\n등록일 {i['date']}\n{i['link']}")

    seen.update(i["id"] for i in items)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("오류:", e, file=sys.stderr)
        sys.exit(1)

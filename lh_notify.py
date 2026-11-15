import json
import os
import sys
from urllib.parse import unquote

import requests

API_URL = "https://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"
SEEN_FILE = "seen.json"

# 받고 싶은 지역. 응답의 CNP_CD_NM에 이 글자가 들어 있으면 통과합니다.
# None이면 전국 공고를 전부 받습니다.
ONLY_REGION = "서울"

# 받고 싶은 유형만 적으세요. 응답의 UPP_AIS_TP_NM 값 기준입니다.
# 예: ["분양주택", "주거복지"]   None이면 전부 받습니다.
ONLY_TYPES = None


def fetch_notices():
    r = requests.get(
        API_URL,
        params={
            "serviceKey": unquote(os.environ["LH_API_KEY"]),
            "PG_SZ": 100,
            "PAGE": 1,
        },
        timeout=30,
    )
    r.raise_for_status()
    for part in r.json():
        if "dsList" in part:
            return part["dsList"]
    raise RuntimeError("dsList를 찾지 못했습니다: " + r.text[:300])


def send_telegram(text):
    r = requests.post(
        f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/sendMessage",
        data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text},
        timeout=30,
    )
    r.raise_for_status()


def main():
    notices = fetch_notices()
    first_run = not os.path.exists(SEEN_FILE)
    seen = set()
    if not first_run:
        with open(SEEN_FILE, encoding="utf-8") as f:
            seen = set(json.load(f))

    new = [n for n in notices if n["PAN_ID"] not in seen]

    if first_run:
        send_telegram(
            f"LH 공고 알림 설정 완료. 기존 공고 {len(notices)}건은 알리지 않고 기록만 해 두었습니다."
        )
    else:
        for n in reversed(new):  # 오래된 것부터
            if ONLY_REGION and ONLY_REGION not in n["CNP_CD_NM"]:
                continue
            if ONLY_TYPES and n["UPP_AIS_TP_NM"] not in ONLY_TYPES:
                continue
            send_telegram(
                f"[LH] {n['AIS_TP_CD_NM']} · {n['CNP_CD_NM']}\n"
                f"{n['PAN_NM']}\n"
                f"접수마감 {n['CLSG_DT']}\n"
                f"{n['DTL_URL']}"
            )

    seen.update(n["PAN_ID"] for n in notices)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("오류:", e, file=sys.stderr)
        sys.exit(1)
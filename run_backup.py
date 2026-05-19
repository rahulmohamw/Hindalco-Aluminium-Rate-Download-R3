import os
import datetime
from downloader import download_for_date   # your existing function

BACKFILL_DAYS = 3

today = datetime.date.today()

for i in range(BACKFILL_DAYS):
    check_date = today - datetime.timedelta(days=i)

    filename = f"Downloads/{check_date.strftime('%Y/%b')}/primary-ready-reckoner-{check_date.strftime('%d-%m-%Y')}.pdf"

    if not os.path.exists(filename):
        print(f"[MISS] Trying backfill for {check_date}")

        try:
            success = download_for_date(check_date)
        except Exception as e:
            print(f"[ERROR] {check_date}: {e}")
            success = False

        if success:
            print(f"[SUCCESS] Downloaded {check_date}")
        else:
            print(f"[SKIP] Not available: {check_date}")
    else:
        print(f"[OK] Already exists: {check_date}")

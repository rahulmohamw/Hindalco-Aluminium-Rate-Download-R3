import os
import datetime
import subprocess

BACKFILL_DAYS = 3
today = datetime.date.today()

print(f"[BACKFILL ACTIVE] Checking last {BACKFILL_DAYS} days")

for i in range(BACKFILL_DAYS):
    check_date = today - datetime.timedelta(days=i)

    filename = f"Downloads/{check_date.strftime('%Y/%b')}/primary-ready-reckoner-{check_date.strftime('%d-%m-%Y')}.pdf"

    if not os.path.exists(filename):
        print(f"[MISS] {check_date} → running downloader")

        result = subprocess.run(["python", "downloader.py"])

        if result.returncode == 0:
            print(f"[DONE] downloader executed")
        else:
            print(f"[ERROR] downloader failed")

    else:
        print(f"[OK] Already exists: {check_date}")

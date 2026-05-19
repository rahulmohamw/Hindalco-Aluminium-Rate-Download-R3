import os
import datetime
from downloader import download_for_date  # use your existing function

# ✅ CONFIG (safe window — no inconsistency)
BACKFILL_DAYS = 3   # check last 3 days only

today = datetime.date.today()

for i in range(BACKFILL_DAYS):
    check_date = today - datetime.timedelta(days=i)

    # ✅ define expected filename logic (same as your main script)
    filename = f"Downloads/{check_date.strftime('%Y/%b')}/primary-ready-reckoner-{check_date.strftime('%d-%m-%Y')}.pdf"

    # ✅ Only download if missing
    if not os.path.exists(filename):
        print(f"[MISS] Trying backfill for {check_date}")

        success = download_for_date(check_date)

        if success:
            print(f"[SUCCESS] Downloaded {check_date}")
        else:
            print(f"[SKIP] Not available yet: {check_date}")
    else:
        print(f"[OK] Already exists: {check_date}")
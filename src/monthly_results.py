#!/usr/bin/env python3
"""
Monthly DB Archiver
Run via cron on the 1st of each month:
    0 0 1 * * /usr/bin/python3 /path/to/archive_monthly.py
"""

import os
import shutil
import sqlite3
from datetime import datetime, timedelta
import sys
import dotenv
dotenv.load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, 'sengoku_bot.db')
ARCHIVE_DIR = os.path.join(SCRIPT_DIR, 'archives')
PM2_WEBSITE_NAME = os.getenv("PM2_WEBSITE_NAME", "sengoku-website")

# Create archives directory if it doesn't exist
os.makedirs(ARCHIVE_DIR, exist_ok=True)

class Website():
    def __init__(self):
        with open(os.path.join(os.path.dirname(SCRIPT_DIR), ".env")) as f:
            lines = f.readlines()
            if "TECHNICAL_TIMEOUT" in lines[-1]:
                lines = lines[:-1]
            self.env_content = "".join(lines)

    def _set_technical_timeout(self, timeout_value):
        self.env_content += f"\nTECHNICAL_TIMEOUT='{timeout_value}'"
        with open(os.path.join(os.path.dirname(SCRIPT_DIR), ".env"), 'w') as f:
            f.write(self.env_content)

    def open(self):
        self._set_technical_timeout('0')
        os.system(f"pm2 restart {PM2_WEBSITE_NAME}")

    def close(self):
        self._set_technical_timeout('1')
        os.system(f"pm2 restart {PM2_WEBSITE_NAME}")

def recalculate_monthly_db(now: datetime = None):
    os.environ["SENGOKU_AFTER"] = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S%z")
    os.environ["SENGOKU_BEFORE"] = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S%z")
    os.environ["REACT_TO_MESSAGES"] = "false"
    import collector
    collector.client.run(collector.TOKEN)

def move_db_to_archive(now: datetime):
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    # Generate filename: october_2025.db
    month_name = now.strftime("%B").lower()  # e.g., "october"
    year = now.year
    archive_filename = f"{month_name}_{year}.db"
    archive_path = os.path.join(ARCHIVE_DIR, archive_filename)

    # Prevent overwriting existing archive
    if os.path.exists(archive_path):
        print(f"Error: Archive already exists: {archive_path}")
        print("    This usually means the script ran twice this month.")
        sys.exit(1)

    try:
        # 1. Copy current DB to archive
        print(f"Archiving {DB_PATH} → {archive_path}")
        shutil.copy2(DB_PATH, archive_path)
        print("   → Archive created successfully.")

        # 2. Reset current DB: delete all events
        print("Resetting current database (clearing events)...")
        os.remove(DB_PATH)

    except Exception as e:
        print(f"Error during archiving/reset: {e}")
        sys.exit(1)

    print(f"Monthly archive complete: {archive_filename}")

def main():
    now = datetime.now() - timedelta(days=1)
    website = Website()
    website.close()

    recalculate_monthly_db(now)
    move_db_to_archive(now)

    website.open()


if __name__ == "__main__":
    main()
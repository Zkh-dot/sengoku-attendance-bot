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
import datatypes
import CONSTANTS
import logger
dotenv.load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, 'sengoku_bot.db')
ARCHIVE_DIR = os.path.join(SCRIPT_DIR, 'archives')
PM2_WEBSITE_NAME = os.getenv("PM2_WEBSITE_NAME", "sengoku-website")
lgr = logger.get_logger("collector")

# Create archives directory if it doesn't exist
os.makedirs(ARCHIVE_DIR, exist_ok=True)


def recalculate_monthly_db(now: datetime = None):
    os.environ["SENGOKU_AFTER"] = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S%z")
    os.environ["SENGOKU_BEFORE"] = now.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S%z")
    os.environ["REACT_TO_MESSAGES"] = "false"
    CONSTANTS.TODAY -= timedelta(days=1)
    import collector
    collector.client.run(collector.TOKEN)

def move_db_to_archive(now: datetime):
    if not os.path.exists(DB_PATH):
        lgr.info(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    # Generate filename: october_2025.db
    month_name = now.strftime("%B").lower()  # e.g., "october"
    year = now.year
    archive_filename = f"{month_name}_{year}.db"
    archive_path = os.path.join(ARCHIVE_DIR, archive_filename)

    # Prevent overwriting existing archive
    if os.path.exists(archive_path):
        lgr.info(f"Error: Archive already exists: {archive_path}")
        lgr.info("    This usually means the script ran twice this month.")

    try:
        # 1. Copy current DB to archive
        lgr.info(f"Archiving {DB_PATH} → {archive_path}")
        shutil.copy2(DB_PATH, archive_path)

        # 2. Reset current DB: delete all events
        lgr.info("Resetting current database (clearing events)...")
        os.remove(DB_PATH)

    except Exception as e:
        lgr.info(f"Error during archiving/reset: {e}")
        sys.exit(1)

    lgr.info(f"Monthly archive complete: {archive_filename}")

def main():
    now = datetime.now() - timedelta(days=1)
    website = datatypes.Website()
    website.close()

    recalculate_monthly_db(now)
    move_db_to_archive(now)

if __name__ == "__main__":
    main()
import os

# Every secret comes from an environment variable. The defaults are only
# for running on your own laptop.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEV_SECRET_KEY = "dev-only-change-me"
SECRET_KEY = os.environ.get("SECRET_KEY", DEV_SECRET_KEY)
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DEFAULT_TZ = os.environ.get("DASHQ_TZ", "Asia/Kolkata")

# WAL lets people read while someone writes. If SQLite ever gives "disk I/O" or
# locking errors on Azure's shared /home disk, set DASHQ_JOURNAL_MODE=DELETE.
JOURNAL_MODE = os.environ.get("DASHQ_JOURNAL_MODE", "WAL").upper()
if JOURNAL_MODE not in ("WAL", "DELETE"):
    JOURNAL_MODE = "WAL"

# Azure App Service always sets WEBSITE_SITE_NAME. DASHQ_ENV=production does the same anywhere else.
IS_PRODUCTION = bool(os.environ.get("WEBSITE_SITE_NAME")) or os.environ.get("DASHQ_ENV") == "production"

# In production we always run behind HTTPS, so cookies are only sent over HTTPS.
# Locally we use plain http, so this is off unless the env var says so.
COOKIE_SECURE = IS_PRODUCTION or os.environ.get("COOKIE_SECURE", "0") == "1"

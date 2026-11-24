"""dashQ: start here.  Run:  python main.py   then open http://localhost:5050

Everything is Python. NiceGUI turns the Python on the server into the web page:
each ui.button(...), ui.label(...) here appears in the browser, and clicks come
back to our Python functions over a live connection (a WebSocket).
"""
import os

from fastapi import HTTPException, Request, Response
from nicegui import app, ui
from starlette.middleware.base import BaseHTTPMiddleware

import config
import db
from services import accounts, pages
from services.qr import make_qr_png
from services.sample_data import make_demo_businesses
from services.sound import beep_wav

# Importing the page modules registers their @ui.page addresses
from views import analytics_page, auth_pages, board, customer, landing, settings_page  # noqa: F401

if config.IS_PRODUCTION and (config.SECRET_KEY == config.DEV_SECRET_KEY or len(config.SECRET_KEY) < 32):
    raise RuntimeError("Set a long random SECRET_KEY in the Azure app settings.")

database = db.connect(os.path.join(config.DATA_DIR, "dashq.db"), config.JOURNAL_MODE)
for line in make_demo_businesses(database):     # the two sample businesses (skipped if they exist)
    print(line)

app.add_static_files("/static", os.path.join(config.BASE_DIR, "static"))

ALERT_SOUND = beep_wav()      # made once when the app starts


# ---------- plain files (not pages) ----------

@app.get("/alert.wav")
def alert_sound():
    return Response(ALERT_SOUND, media_type="audio/wav", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/qr/{slug}.png")
def qr_png(request: Request, slug: str, via: str = "qr", download: int = 0):
    business = accounts.get_business_by_slug(db.get_db(), slug)
    if business is None:
        raise HTTPException(404)
    # The QR code holds the customer link, e.g. https://dashq.azurewebsites.net/b/encave-cafe
    link = str(request.base_url).rstrip("/") + f"/b/{slug}" + ("?via=nfc" if via == "nfc" else "")
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="dashq-{slug}.png"'
    return Response(make_qr_png(link), media_type="image/png", headers=headers)


@app.get("/b/{slug}/img/{filename}")
def picture(slug: str, filename: str):
    business = accounts.get_business_by_slug(db.get_db(), slug)
    if business is None or not pages.has_image(db.get_db(), business["id"], filename):
        raise HTTPException(404)
    path = os.path.join(pages.folder_for(config.DATA_DIR, business["id"]), os.path.basename(filename))
    with open(path, "rb") as file:
        return Response(file.read(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


# ---------- security headers on every response ----------

async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if config.IS_PRODUCTION:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response

app.add_middleware(BaseHTTPMiddleware, dispatch=security_headers)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="dashQ",
        port=config.PORT,
        favicon=os.path.join(config.BASE_DIR, "static", "img", "favicon.svg"),
        storage_secret=config.SECRET_KEY,
        session_middleware_kwargs={"max_age": config.COOKIE_DAYS * 24 * 3600, "https_only": config.IS_PRODUCTION},
        reload=not config.IS_PRODUCTION,
        show=False,
        language="en-US",
        forwarded_allow_ips="*",        # Azure handles HTTPS in front of us
        proxy_headers=True,
    )

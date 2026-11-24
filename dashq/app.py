import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

import config
import db
from auth import auth
from sections.customer import customer
from sections.dashboard import dashboard
from sections.landing import landing

csrf = CSRFProtect()

# Sent with every page. The Content-Security-Policy only lets the browser run
# our own scripts, so even if someone sneaks HTML into a page, their script won't run.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; media-src 'self'; "
        "frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def create_app(test_config=None):
    app = Flask(__name__)
    # Azure sits in front of the app and handles HTTPS. This makes url_for(..., _external=True)
    # build https:// links (for the QR code) instead of http://
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["DATA_DIR"] = config.DATA_DIR
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = config.COOKIE_SECURE
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # The cookie that remembers a customer's place in line (and the owner's login) lasts 2 days
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=2)
    # Uploads bigger than 5 MB are refused before they reach our code
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    # Tests pass their own settings (for example a temporary DATA_DIR)
    if test_config:
        app.config.update(test_config)

    # Refuse to start on the internet with the laptop secret key
    if config.IS_PRODUCTION and not app.config.get("TESTING"):
        if app.config["SECRET_KEY"] == config.DEV_SECRET_KEY or len(app.config["SECRET_KEY"]) < 32:
            raise RuntimeError("Set a long random SECRET_KEY in the Azure app settings.")

    os.makedirs(app.config["DATA_DIR"], exist_ok=True)
    app.config["DATABASE"] = os.path.join(app.config["DATA_DIR"], "dashq.db")
    db.init_db(app.config["DATABASE"], config.JOURNAL_MODE)
    app.teardown_appcontext(db.close_db)

    csrf.init_app(app)

    @app.after_request
    def add_security_headers(response):
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if app.config["SESSION_COOKIE_SECURE"]:
            # Tell browsers to only ever use HTTPS for this site
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    # Friendly error pages. In production Flask never shows a stack trace.
    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/error.html", code=404, title="We can't find that page",
                               text="The link may be old or mistyped."), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/error.html", code=500, title="Something went wrong on our side",
                               text="Please try again in a moment. If it keeps happening, tell the staff."), 500

    @app.errorhandler(CSRFError)
    def form_expired(error):
        return render_template("errors/error.html", code=400, title="This form has expired",
                               text="Go back, refresh the page and try again."), 400

    @app.errorhandler(413)
    def too_big(error):
        flash("That file is too big. The limit is 4 MB.", "error")
        return redirect(request.referrer or url_for("landing.home"))

    # {{ some_time|local_time }} shows a saved UTC time as HH:MM in the business's timezone
    @app.template_filter("local_time")
    def local_time(text, timezone_name=config.DEFAULT_TZ):
        moment = datetime.fromisoformat(text).astimezone(ZoneInfo(timezone_name))
        return moment.strftime("%H:%M")

    app.register_blueprint(landing)
    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(customer)

    # flask --app app:create_app seed-demo   ->  makes the two sample businesses with 30 days of history
    @app.cli.command("seed-demo")
    def seed_demo_command():
        from services.sample_data import make_demo_businesses
        with app.app_context():
            for line in make_demo_businesses(db.get_db()):
                print(line)

    return app

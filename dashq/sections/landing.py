from flask import Blueprint, Response, render_template

from services.sound import beep_wav

landing = Blueprint("landing", __name__)

ALERT_SOUND = beep_wav()      # made once when the app starts


@landing.route("/")
def home():
    return render_template("landing/index.html")


@landing.route("/alert.wav")
def alert_sound():
    response = Response(ALERT_SOUND, mimetype="audio/wav")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response

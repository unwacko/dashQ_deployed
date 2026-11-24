"""Sign up, log in, log out, and the "must be logged in" decorator.
Anyone can make an account and start straight away."""
from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from db import get_db
from services import accounts

auth = Blueprint("auth", __name__)


@auth.route("/app/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        business_id, error = accounts.create_business(
            get_db(),
            request.form.get("name", ""),
            request.form.get("email", ""),
            request.form.get("password", ""),
            request.form.get("category", ""),
        )
        if error:
            flash(error, "error")
            return render_template("auth/signup.html", form=request.form,
                                   categories=accounts.CATEGORIES), 400
        session.clear()
        session["business_id"] = business_id
        session.permanent = True
        return redirect(url_for("dashboard.board", welcome=1))
    form = {"email": request.args.get("email", "")}
    return render_template("auth/signup.html", form=form, categories=accounts.CATEGORIES)


@auth.route("/app/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        business, error = accounts.check_login(
            get_db(), request.form.get("email", ""), request.form.get("password", "")
        )
        if error:
            flash(error, "error")
            return render_template("auth/login.html", form=request.form), 400
        session.clear()
        session["business_id"] = business["id"]
        session.permanent = True
        return redirect(url_for("dashboard.board"))
    return render_template("auth/login.html", form={})


@auth.route("/app/demo/<which>", methods=["POST"])
def demo_login(which):
    # One click into the sample accounts from the landing page (made by: flask seed-demo)
    emails = {"encave": "encave@demo.dashq.in", "sociovate": "sociovate@demo.dashq.in"}
    business = accounts.find_by_email(get_db(), emails.get(which, ""))
    if business is None:
        flash("The demo accounts aren't set up yet. Run: flask --app app:create_app seed-demo", "error")
        return redirect(url_for("auth.login"))
    session.clear()
    session["business_id"] = business["id"]
    return redirect(url_for("dashboard.board"))


@auth.route("/app/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("landing.home"))


def login_required(view):
    # Loads the logged-in business into g.business, or sends you to the login page
    @wraps(view)
    def wrapper(*args, **kwargs):
        business_id = session.get("business_id")
        business = None
        if business_id is not None:
            business = accounts.get_business(get_db(), business_id)
        if business is None:
            session.pop("business_id", None)
            return redirect(url_for("auth.login"))
        g.business = business
        return view(*args, **kwargs)
    return wrapper

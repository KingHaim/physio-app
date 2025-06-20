from flask import Blueprint, render_template

legal = Blueprint('legal', __name__)

@legal.route("/privacy")
def privacy():
    return render_template("legal/privacy_policy.html")

@legal.route("/terms")
def terms():
    return render_template("legal/terms_and_conditions.html") 
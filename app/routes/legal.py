from flask import Blueprint, render_template, request

legal = Blueprint('legal', __name__)

@legal.route("/privacy")
def privacy():
    return render_template("legal/privacy_policy.html")

@legal.route("/terms")
def terms():
    return render_template("legal/terms_and_conditions.html")

@legal.route("/dpa", methods=["GET", "POST"])
def dpa():
    clinic_name = ""
    clinic_address = ""
    clinic_rep = ""
    if request.method == "POST":
        clinic_name = request.form.get("clinic_name", "")
        clinic_address = request.form.get("clinic_address", "")
        clinic_rep = request.form.get("clinic_rep", "")
    return render_template(
        "legal/dpa.html",
        clinic_name=clinic_name,
        clinic_address=clinic_address,
        clinic_rep=clinic_rep
    ) 
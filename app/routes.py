from flask import Blueprint, render_template

# Create a Blueprint object
main = Blueprint("main", __name__)


@main.route("/")
def home():
    return render_template("index.html", title="AI Career Intelligence")


@main.route("/about")
def about():
    return render_template("about.html", title="About - AI Career Intelligence")
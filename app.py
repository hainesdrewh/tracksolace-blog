import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps

import bleach
import markdown as md
from dotenv import load_dotenv
from flask import (
    Flask, abort, g, redirect, render_template, request,
    session, url_for, Response, flash
)
from werkzeug.security import check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") != "development"

DATABASE_PATH = os.environ.get("DATABASE_PATH", "blog.db")
ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD_HASH = os.environ["ADMIN_PASSWORD_HASH"]
SITE_URL = os.environ.get("SITE_URL", "https://blog.tracksolace.xyz")

ALLOWED_TAGS = [
    "p", "br", "hr", "strong", "em", "code", "pre", "blockquote",
    "ul", "ol", "li", "a", "h2", "h3", "h4", "img", "table", "thead",
    "tbody", "tr", "th", "td", "del", "input",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "loading"],
    "input": ["type", "checked", "disabled"],
}

# In-memory login attempt tracking. Fine for a single-admin, low-traffic
# blog on one process; a persistent store would be overkill here.
_login_attempts = {}
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            body_md TEXT NOT NULL,
            excerpt TEXT NOT NULL,
            published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    db.commit()


def slugify(title):
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or secrets.token_hex(4)


def render_markdown(body_md):
    html = md.markdown(body_md, extensions=["fenced_code", "tables"])
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_minutes(body_md):
    words = len(body_md.split())
    return max(1, round(words / 200))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get("_csrf_token")
        submitted = request.form.get("_csrf_token")
        if not token or not submitted or not secrets.compare_digest(token, submitted):
            abort(400)


@app.context_processor
def inject_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return {"csrf_token": session["_csrf_token"], "site_url": SITE_URL}


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; base-uri 'self'; frame-ancestors 'none'"
    )
    return response


# ---------- Public routes ----------

@app.route("/")
def index():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM posts WHERE published = 1 ORDER BY created_at DESC"
    ).fetchall()
    posts = [dict(row, read_minutes=read_minutes(row["body_md"])) for row in rows]
    return render_template("index.html", posts=posts)


@app.route("/post/<slug>")
def view_post(slug):
    db = get_db()
    row = db.execute(
        "SELECT * FROM posts WHERE slug = ? AND published = 1", (slug,)
    ).fetchone()
    if row is None:
        abort(404)
    post = dict(row, read_minutes=read_minutes(row["body_md"]))
    return render_template("post.html", post=post, content_html=render_markdown(post["body_md"]))


@app.route("/rss.xml")
def rss():
    db = get_db()
    posts = db.execute(
        "SELECT * FROM posts WHERE published = 1 ORDER BY created_at DESC LIMIT 30"
    ).fetchall()
    xml = render_template("rss.xml", posts=posts)
    return Response(xml, mimetype="application/rss+xml")


@app.route("/sitemap.xml")
def sitemap():
    db = get_db()
    posts = db.execute("SELECT slug, updated_at FROM posts WHERE published = 1").fetchall()
    xml = render_template("sitemap.xml", posts=posts)
    return Response(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    body = f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


# ---------- Admin routes ----------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html")

    ip = request.remote_addr or "unknown"
    attempts = _login_attempts.get(ip, [])
    attempts = [t for t in attempts if time.time() - t < LOGIN_WINDOW_SECONDS]
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        flash("Too many login attempts. Try again in a few minutes.")
        return render_template("admin_login.html"), 429

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    valid = secrets.compare_digest(username, ADMIN_USERNAME) and check_password_hash(
        ADMIN_PASSWORD_HASH, password
    )
    if not valid:
        attempts.append(time.time())
        _login_attempts[ip] = attempts
        flash("Incorrect username or password.")
        return render_template("admin_login.html"), 401

    _login_attempts.pop(ip, None)
    session.clear()
    session["is_admin"] = True
    session["_csrf_token"] = secrets.token_hex(32)
    next_path = request.args.get("next")
    return redirect(next_path if next_path and next_path.startswith("/admin") else url_for("admin_dashboard"))


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    posts = db.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()
    return render_template("admin_dashboard.html", posts=posts)


@app.route("/admin/new", methods=["GET", "POST"])
@login_required
def admin_new():
    if request.method == "GET":
        return render_template("admin_edit.html", post=None)

    title = request.form.get("title", "").strip()
    body_md = request.form.get("body_md", "").strip()
    excerpt = request.form.get("excerpt", "").strip()
    published = 1 if request.form.get("published") else 0
    if not title or not body_md:
        flash("Title and body are required.")
        return render_template("admin_edit.html", post=None), 400

    slug = slugify(request.form.get("slug") or title)
    timestamp = now_iso()
    db = get_db()
    try:
        db.execute(
            "INSERT INTO posts (slug, title, body_md, excerpt, published, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (slug, title, body_md, excerpt or body_md[:160], published, timestamp, timestamp),
        )
        db.commit()
    except sqlite3.IntegrityError:
        flash("That slug is already in use. Choose a different one.")
        return render_template("admin_edit.html", post=None), 400
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/edit/<int:post_id>", methods=["GET", "POST"])
@login_required
def admin_edit(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if post is None:
        abort(404)

    if request.method == "GET":
        return render_template("admin_edit.html", post=post)

    title = request.form.get("title", "").strip()
    body_md = request.form.get("body_md", "").strip()
    excerpt = request.form.get("excerpt", "").strip()
    published = 1 if request.form.get("published") else 0
    if not title or not body_md:
        flash("Title and body are required.")
        return render_template("admin_edit.html", post=post), 400

    slug = slugify(request.form.get("slug") or title)
    try:
        db.execute(
            "UPDATE posts SET slug=?, title=?, body_md=?, excerpt=?, published=?, updated_at=? WHERE id=?",
            (slug, title, body_md, excerpt or body_md[:160], published, now_iso(), post_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        flash("That slug is already in use. Choose a different one.")
        return render_template("admin_edit.html", post=post), 400
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete/<int:post_id>", methods=["POST"])
@login_required
def admin_delete(post_id):
    db = get_db()
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True, port=8773)

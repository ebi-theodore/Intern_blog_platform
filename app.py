import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parent


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-this-secret"),
        DATABASE=os.environ.get("DATABASE", str(Path(app.instance_path) / "blog.sqlite3")),
        MAX_CONTENT_LENGTH=1_000_000,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    def initialize_database():
        db = sqlite3.connect(app.config["DATABASE"])
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                body TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Notes',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS posts_created_at ON posts(created_at DESC);
            CREATE INDEX IF NOT EXISTS comments_post_id ON comments(post_id, created_at);
            """
        )
        db.commit()
        db.close()

    initialize_database()

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def user_payload(user):
        return {"id": user["id"], "username": user["username"], "email": user["email"]}

    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        return get_db().execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,)).fetchone()

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user() is None:
                return jsonify(error="Please sign in to continue."), 401
            return view(*args, **kwargs)
        return wrapped

    @app.before_request
    def protect_mutations():
        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("csrf_token")
            provided = request.headers.get("X-CSRF-Token")
            if not expected or not provided or not secrets.compare_digest(expected, provided):
                return jsonify(error="Your session token expired. Refresh and try again."), 403

    def json_body():
        return request.get_json(silent=True) or {}

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/auth/csrf")
    def csrf_token():
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return jsonify(csrfToken=session["csrf_token"])

    @app.get("/api/auth/me")
    def who_am_i():
        user = current_user()
        return jsonify(user=user_payload(user) if user else None)

    @app.post("/api/auth/register")
    def register():
        data = json_body()
        username = str(data.get("username", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        if not re.fullmatch(r"[A-Za-z0-9_ -]{2,24}", username):
            return jsonify(error="Name must be 2–24 characters and use letters, numbers, spaces, _ or -."), 400
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
            return jsonify(error="Enter a valid email address."), 400
        if len(password) < 8 or len(password) > 128:
            return jsonify(error="Password must be between 8 and 128 characters."), 400
        db = get_db()
        try:
            cursor = db.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (username, email, generate_password_hash(password), now()),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return jsonify(error="That name or email is already registered."), 409
        session.clear()
        session["user_id"] = cursor.lastrowid
        session["csrf_token"] = secrets.token_urlsafe(32)
        user = db.execute("SELECT id, username, email FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(user=user_payload(user)), 201

    @app.post("/api/auth/login")
    def login():
        data = json_body()
        identity = str(data.get("identity", "")).strip()
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE",
            (identity, identity),
        ).fetchone()
        if not user or not check_password_hash(user["password_hash"], str(data.get("password", ""))):
            return jsonify(error="The email/name or password doesn’t match."), 401
        session.clear()
        session["user_id"] = user["id"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify(user=user_payload(user))

    @app.post("/api/auth/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/posts")
    def list_posts():
        query = str(request.args.get("q", "")).strip()[:100]
        category = str(request.args.get("category", "")).strip()[:40]
        clauses, params = [], []
        if query:
            term = f"%{query}%"
            clauses.append("(p.title LIKE ? OR p.excerpt LIKE ? OR p.body LIKE ? OR u.username LIKE ?)")
            params.extend([term] * 4)
        if category and category.lower() != "all stories":
            clauses.append("p.category = ? COLLATE NOCASE")
            params.append(category)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        posts = get_db().execute(
            f"""SELECT p.id, p.title, p.excerpt, p.body, p.category, p.created_at, p.updated_at,
                       u.id AS author_id, u.username AS author,
                       (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count
                FROM posts p JOIN users u ON u.id = p.user_id {where}
                ORDER BY p.created_at DESC""",
            params,
        ).fetchall()
        return jsonify(posts=[dict(row) for row in posts])

    @app.get("/api/posts/<int:post_id>")
    def get_post(post_id):
        db = get_db()
        post = db.execute(
            """SELECT p.id, p.title, p.excerpt, p.body, p.category, p.created_at, p.updated_at,
                      u.id AS author_id, u.username AS author
               FROM posts p JOIN users u ON u.id = p.user_id WHERE p.id = ?""",
            (post_id,),
        ).fetchone()
        if post is None:
            return jsonify(error="Story not found."), 404
        comments = db.execute(
            """SELECT c.id, c.body, c.created_at, u.id AS author_id, u.username AS author
               FROM comments c JOIN users u ON u.id = c.user_id
               WHERE c.post_id = ? ORDER BY c.created_at ASC""",
            (post_id,),
        ).fetchall()
        return jsonify(post=dict(post), comments=[dict(row) for row in comments])

    def validate_post(data):
        title = str(data.get("title", "")).strip()
        body = str(data.get("body", "")).strip()
        category = str(data.get("category", "Notes")).strip() or "Notes"
        if not title or len(title) > 120:
            return None, "Title is required and must be 120 characters or fewer."
        if len(body) < 20 or len(body) > 20000:
            return None, "Story must be between 20 and 20,000 characters."
        if len(category) > 40:
            return None, "Category must be 40 characters or fewer."
        excerpt = str(data.get("excerpt", "")).strip()[:220] or body[:180].rsplit(" ", 1)[0]
        return {"title": title, "excerpt": excerpt, "body": body, "category": category}, None

    @app.post("/api/posts")
    @login_required
    def create_post():
        post, error = validate_post(json_body())
        if error:
            return jsonify(error=error), 400
        db = get_db()
        stamp = now()
        cursor = db.execute(
            "INSERT INTO posts (user_id, title, excerpt, body, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session["user_id"], post["title"], post["excerpt"], post["body"], post["category"], stamp, stamp),
        )
        db.commit()
        return jsonify(id=cursor.lastrowid), 201

    @app.put("/api/posts/<int:post_id>")
    @login_required
    def edit_post(post_id):
        db = get_db()
        existing = db.execute("SELECT user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
        if existing is None:
            return jsonify(error="Story not found."), 404
        if existing["user_id"] != session["user_id"]:
            return jsonify(error="You can only edit your own stories."), 403
        post, error = validate_post(json_body())
        if error:
            return jsonify(error=error), 400
        db.execute(
            "UPDATE posts SET title = ?, excerpt = ?, body = ?, category = ?, updated_at = ? WHERE id = ?",
            (post["title"], post["excerpt"], post["body"], post["category"], now(), post_id),
        )
        db.commit()
        return jsonify(ok=True)

    @app.delete("/api/posts/<int:post_id>")
    @login_required
    def delete_post(post_id):
        db = get_db()
        existing = db.execute("SELECT user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
        if existing is None:
            return jsonify(error="Story not found."), 404
        if existing["user_id"] != session["user_id"]:
            return jsonify(error="You can only delete your own stories."), 403
        db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        db.commit()
        return jsonify(ok=True)

    @app.post("/api/posts/<int:post_id>/comments")
    @login_required
    def add_comment(post_id):
        db = get_db()
        if db.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,)).fetchone() is None:
            return jsonify(error="Story not found."), 404
        body = str(json_body().get("body", "")).strip()
        if not body or len(body) > 2000:
            return jsonify(error="Comment must be between 1 and 2,000 characters."), 400
        cursor = db.execute(
            "INSERT INTO comments (post_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
            (post_id, session["user_id"], body, now()),
        )
        db.commit()
        return jsonify(id=cursor.lastrowid), 201

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify(error="Request is too large."), 413

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")

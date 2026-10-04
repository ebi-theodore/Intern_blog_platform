# Commonplace

A full-stack blogging platform built with Flask, SQLite, and plain HTML, CSS, and JavaScript. Readers can discover and search stories, registered members can publish and manage their own posts, and signed-in users can leave comments.

## Requirements

- Python 3.10 or newer
- pip

## Run on Windows

1. Open a terminal in this folder and create a virtual environment:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

2. Install the dependency:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Start the development server:

   ```powershell
   python app.py
   ```

4. Visit `http://127.0.0.1:5000` in your browser. The SQLite database is created automatically in the `instance` folder.

## Features

- User registration, sign-in, and sign-out with Werkzeug password hashing.
- Session-based authentication and CSRF tokens on API writes.
- Create, edit, and delete your own posts; browse, search, and filter all posts.
- Comment on posts while signed in.
- SQLite schema initialization, parameterized queries, basic validation, and responsive UI.

## REST API

- `GET /api/posts?q=&category=` — list/filter posts
- `GET /api/posts/<id>` — read a post and comments
- `POST /api/posts` — publish (signed in)
- `PUT /api/posts/<id>` / `DELETE /api/posts/<id>` — manage your own post
- `POST /api/posts/<id>/comments` — comment (signed in)
- `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
- `GET /api/auth/csrf` — retrieve the session token required as `X-CSRF-Token` for write requests

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Deployment note

Set a unique, unpredictable `SECRET_KEY` in the environment. Do not use Flask's development server or `FLASK_DEBUG=1` in production. Serve the application behind a production WSGI server over HTTPS.

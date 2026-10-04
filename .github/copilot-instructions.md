# Commonplace blog platform

- Backend: Flask REST API with SQLite; initialize the database through `create_app()`.
- Frontend: vanilla JavaScript in `static/app.js`, styles in `static/styles.css`, template in `templates/index.html`.
- Keep API writes authenticated and protected by the session CSRF token (`X-CSRF-Token`).
- Preserve ownership checks for post editing/deletion and escape user-generated content in the browser.
- Run tests with `python -m unittest discover -s tests`.

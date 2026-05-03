"""Entrypoint.

- Local dev:  ``python wsgi.py`` (Flask dev server, debug ON by default).
- Production: ``gunicorn wsgi:app`` (gunicorn imports ``app`` directly).
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )

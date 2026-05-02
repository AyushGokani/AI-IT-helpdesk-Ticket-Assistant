"""Production / dev entrypoint: ``python wsgi.py``."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )

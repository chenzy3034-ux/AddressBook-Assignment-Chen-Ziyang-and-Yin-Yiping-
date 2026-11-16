import os
from urllib.parse import urlsplit

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

from app import create_app
from app.db import get_db


public_url = urlsplit(os.environ["ADDRESS_BOOK_URL"])
mount_path = public_url.path.rstrip("/")
app = create_app(
    {
        "SECRET_KEY": os.environ["ADDRESS_BOOK_SECRET"],
        "DATABASE": os.path.join(os.environ["STATE_DIRECTORY"], "address_book.sqlite"),
        "TRUSTED_HOSTS": [public_url.hostname],
        "APPLICATION_ROOT": mount_path,
        "SESSION_COOKIE_NAME": "address_book_session",
        "SESSION_COOKIE_SECURE": True,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Strict",
        "MAX_CONTENT_LENGTH": 6 * 1024 * 1024,
        "MAX_FORM_MEMORY_SIZE": 256 * 1024,
        "MAX_FORM_PARTS": 150,
        "CSRF_ENABLED": True,
    }
)


@app.get("/health")
def health():
    get_db().execute("SELECT 1 FROM contacts LIMIT 1").fetchone()
    return {"status": "ok"}


@app.after_request
def prevent_shared_caching(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


application = DispatcherMiddleware(Response(status=404), {mount_path: app})

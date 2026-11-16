import os
import secrets

from flask import Flask, abort, render_template, request, session


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="development-only-key",
        DATABASE=os.path.join(app.instance_path, "address_book.sqlite"),
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    if app.config["DATABASE"] != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)

    if app.config.get("CSRF_ENABLED"):
        @app.template_global()
        def csrf_token():
            if "csrf_token" not in session:
                session["csrf_token"] = secrets.token_hex(32)
            return session["csrf_token"]

        @app.before_request
        def verify_csrf():
            if request.method == "POST":
                expected = session.get("csrf_token", "")
                provided = request.form.get("csrf_token", "")
                if not expected or not secrets.compare_digest(
                    expected.encode("utf-8"), provided.encode("utf-8")
                ):
                    abort(403)

    from . import db

    db.init_app(app)

    from .contacts import bp

    app.register_blueprint(bp)

    from .excel import bp as excel_bp

    app.register_blueprint(excel_bp)

    with app.app_context():
        db.init_db()

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("not_found.html"), 404

    return app

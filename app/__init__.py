import os

from flask import Flask, render_template


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="development-only-key",
        DATABASE=os.path.join(app.instance_path, "address_book.sqlite"),
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

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

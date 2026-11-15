import sqlite3

import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(error=None):
    database = g.pop("db", None)

    if database is not None:
        database.close()


def init_db():
    database = get_db()

    with current_app.open_resource("schema.sql") as schema_file:
        database.executescript(schema_file.read().decode("utf-8"))

    columns = {
        column["name"] for column in database.execute("PRAGMA table_info(contacts)")
    }
    if "is_favorite" not in columns:
        database.execute(
            "ALTER TABLE contacts ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0"
        )
        database.commit()


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Initialized the database.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

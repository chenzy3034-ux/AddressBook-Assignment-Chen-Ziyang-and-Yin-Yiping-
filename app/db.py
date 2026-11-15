import sqlite3

import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

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

    migration_name = "move_legacy_contact_methods"
    migration = database.execute(
        "SELECT 1 FROM schema_migrations WHERE name = ?", (migration_name,)
    ).fetchone()
    if migration is None:
        legacy_method_columns = ("phone", "email", "address")
        available_legacy_columns = [
            name for name in legacy_method_columns if name in columns
        ]

        with database:
            if available_legacy_columns:
                selected_columns = ", ".join(available_legacy_columns)
                contacts = database.execute(
                    f"SELECT id, {selected_columns} FROM contacts"
                ).fetchall()
                for contact in contacts:
                    for sort_order, method_type in enumerate(
                        available_legacy_columns
                    ):
                        value = contact[method_type].strip()
                        if value:
                            database.execute(
                                """
                                INSERT INTO contact_methods
                                    (contact_id, method_type, value, sort_order)
                                VALUES (?, ?, ?, ?)
                                """,
                                (contact["id"], method_type, value, sort_order),
                            )

            database.execute(
                "INSERT INTO schema_migrations (name) VALUES (?)",
                (migration_name,),
            )


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Initialized the database.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

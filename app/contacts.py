from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .db import get_db


bp = Blueprint("contacts", __name__)


def get_contact(contact_id):
    contact = get_db().execute(
        "SELECT * FROM contacts WHERE id = ?", (contact_id,)
    ).fetchone()

    if contact is None:
        abort(404)

    return contact


def validate_contact_form(form):
    values = {
        "name": form.get("name", "").strip(),
        "phone": form.get("phone", "").strip(),
        "email": form.get("email", "").strip(),
        "address": form.get("address", "").strip(),
    }
    errors = []

    if not values["name"]:
        errors.append("Name is required.")
    if not any((values["phone"], values["email"], values["address"])):
        errors.append("At least one contact method is required.")

    return values, errors


@bp.route("/")
def index():
    contacts = get_db().execute(
        "SELECT * FROM contacts ORDER BY name COLLATE NOCASE, id"
    ).fetchall()
    return render_template("contact_list.html", contacts=contacts)


@bp.route("/contacts/new", methods=("GET", "POST"))
def create():
    values = {"name": "", "phone": "", "email": "", "address": ""}

    if request.method == "POST":
        values, errors = validate_contact_form(request.form)

        if not errors:
            database = get_db()
            cursor = database.execute(
                """
                INSERT INTO contacts (name, phone, email, address)
                VALUES (?, ?, ?, ?)
                """,
                (values["name"], values["phone"], values["email"], values["address"]),
            )
            database.commit()
            flash("Contact created successfully.", "success")
            return redirect(url_for("contacts.detail", contact_id=cursor.lastrowid))

        for error in errors:
            flash(error, "error")

    return render_template(
        "contact_form.html", contact=values, page_title="Add contact"
    )


@bp.route("/contacts/<int:contact_id>")
def detail(contact_id):
    return render_template("contact_detail.html", contact=get_contact(contact_id))


@bp.route("/contacts/<int:contact_id>/edit", methods=("GET", "POST"))
def edit(contact_id):
    contact = get_contact(contact_id)
    values = dict(contact)

    if request.method == "POST":
        values, errors = validate_contact_form(request.form)

        if not errors:
            database = get_db()
            database.execute(
                """
                UPDATE contacts
                SET name = ?, phone = ?, email = ?, address = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    values["name"],
                    values["phone"],
                    values["email"],
                    values["address"],
                    contact_id,
                ),
            )
            database.commit()
            flash("Contact updated successfully.", "success")
            return redirect(url_for("contacts.detail", contact_id=contact_id))

        for error in errors:
            flash(error, "error")

    return render_template(
        "contact_form.html", contact=values, page_title="Edit contact"
    )


@bp.route("/contacts/<int:contact_id>/delete", methods=("POST",))
def delete(contact_id):
    contact = get_contact(contact_id)
    database = get_db()
    database.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    database.commit()
    flash(f"{contact['name']} was deleted.", "success")
    return redirect(url_for("contacts.index"))

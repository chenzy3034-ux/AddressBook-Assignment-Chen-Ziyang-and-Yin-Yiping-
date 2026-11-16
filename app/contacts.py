from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .db import get_db
from .i18n import translate


bp = Blueprint("contacts", __name__)

METHOD_TYPES = {
    "phone": "Phone numbers",
    "email": "Email addresses",
    "social": "Social media",
    "address": "Postal addresses",
}

DEFAULT_METHOD_LABELS = {
    "phone": "Phone",
    "email": "Email",
    "social": "Social",
    "address": "Address",
}


def get_contact(contact_id):
    contact = get_db().execute(
        "SELECT * FROM contacts WHERE id = ?", (contact_id,)
    ).fetchone()

    if contact is None:
        abort(404)

    return contact


def get_contact_methods(contact_id):
    return get_db().execute(
        """
        SELECT * FROM contact_methods
        WHERE contact_id = ?
        ORDER BY sort_order, id
        """,
        (contact_id,),
    ).fetchall()


def validate_contact_form(form):
    values = {"name": form.get("name", "").strip()}
    method_types = form.getlist("method_type")
    method_labels = form.getlist("method_label")
    method_values = form.getlist("method_value")
    row_count = max(len(method_types), len(method_labels), len(method_values))
    submitted_methods = []

    for index in range(row_count):
        method = {
            "method_type": method_types[index] if index < len(method_types) else "",
            "label": method_labels[index].strip()
            if index < len(method_labels)
            else "",
            "value": method_values[index].strip()
            if index < len(method_values)
            else "",
        }
        submitted_methods.append(method)

    if not submitted_methods:
        submitted_methods.append(
            {"method_type": "phone", "label": "", "value": ""}
        )

    errors = []

    if not values["name"]:
        errors.append("Name is required.")

    methods = [method for method in submitted_methods if method["value"]]
    if not methods:
        errors.append("At least one contact method is required.")

    if any(method["method_type"] not in METHOD_TYPES for method in methods):
        errors.append("Select a valid contact method type.")

    return values, submitted_methods, methods, errors


def insert_contact_methods(database, contact_id, methods):
    database.executemany(
        """
        INSERT INTO contact_methods
            (contact_id, method_type, label, value, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                contact_id,
                method["method_type"],
                method["label"],
                method["value"],
                sort_order,
            )
            for sort_order, method in enumerate(methods)
        ],
    )


@bp.route("/")
def index():
    active_filter = request.args.get("filter", "all")
    if active_filter not in ("all", "favorites"):
        active_filter = "all"
    search_query = request.args.get("q", "").strip()[:120]

    query = """
        SELECT contacts.*,
            (
                SELECT value FROM contact_methods
                WHERE contact_id = contacts.id AND method_type = 'phone'
                ORDER BY sort_order, id LIMIT 1
            ) AS primary_phone,
            (
                SELECT value FROM contact_methods
                WHERE contact_id = contacts.id AND method_type = 'email'
                ORDER BY sort_order, id LIMIT 1
            ) AS primary_email
        FROM contacts
    """
    conditions = []
    parameters = []
    if active_filter == "favorites":
        conditions.append("contacts.is_favorite = 1")
    if search_query:
        escaped_query = (
            search_query.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        search_pattern = f"%{escaped_query}%"
        conditions.append(
            """
            (
                contacts.name LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR EXISTS (
                    SELECT 1 FROM contact_methods AS search_methods
                    WHERE search_methods.contact_id = contacts.id
                    AND (
                        search_methods.value LIKE ? ESCAPE '\\' COLLATE NOCASE
                        OR search_methods.label LIKE ? ESCAPE '\\' COLLATE NOCASE
                    )
                )
            )
            """
        )
        parameters.extend([search_pattern, search_pattern, search_pattern])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY contacts.name COLLATE NOCASE, contacts.id"

    database = get_db()
    with database:
        database.execute("BEGIN")
        contacts = database.execute(query, parameters).fetchall()
        total_contacts = database.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    return render_template(
        "contact_list.html",
        contacts=contacts,
        total_contacts=total_contacts,
        active_filter=active_filter,
        search_query=search_query,
    )


@bp.route("/contacts/new", methods=("GET", "POST"))
def create():
    values = {"name": ""}
    methods = [{"method_type": "phone", "label": "", "value": ""}]

    if request.method == "POST":
        values, submitted_methods, valid_methods, errors = validate_contact_form(
            request.form
        )
        methods = submitted_methods

        if not errors:
            database = get_db()
            with database:
                cursor = database.execute(
                    "INSERT INTO contacts (name) VALUES (?)", (values["name"],)
                )
                insert_contact_methods(database, cursor.lastrowid, valid_methods)
            flash(translate("Contact created successfully."), "success")
            return redirect(url_for("contacts.detail", contact_id=cursor.lastrowid))

        for error in errors:
            flash(translate(error), "error")

    return render_template(
        "contact_form.html",
        contact=values,
        methods=methods,
        method_types=METHOD_TYPES,
        page_title="Add contact",
    )


@bp.route("/contacts/<int:contact_id>")
def detail(contact_id):
    contact = get_contact(contact_id)
    methods = get_contact_methods(contact_id)
    method_sections = [
        {
            "method_type": method_type,
            "title": title,
            "methods": [
                {
                    "label": method["label"]
                    or translate(DEFAULT_METHOD_LABELS[method_type]),
                    "value": method["value"],
                }
                for method in methods
                if method["method_type"] == method_type
            ],
        }
        for method_type, title in METHOD_TYPES.items()
    ]
    return render_template(
        "contact_detail.html", contact=contact, method_sections=method_sections
    )


@bp.route("/contacts/<int:contact_id>/favorite", methods=("POST",))
def toggle_favorite(contact_id):
    contact = get_contact(contact_id)
    is_favorite = 0 if contact["is_favorite"] else 1
    database = get_db()
    database.execute(
        """
        UPDATE contacts
        SET is_favorite = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (is_favorite, contact_id),
    )
    database.commit()

    if is_favorite:
        flash(translate("{name} was added to favorites.", name=contact["name"]), "success")
    else:
        flash(translate("{name} was removed from favorites.", name=contact["name"]), "success")

    active_filter = request.form.get("filter", "all")
    if active_filter not in ("all", "favorites"):
        active_filter = "all"
    search_query = request.form.get("q", "").strip()[:120]
    return redirect(
        url_for("contacts.index", filter=active_filter, q=search_query)
    )


@bp.route("/contacts/<int:contact_id>/edit", methods=("GET", "POST"))
def edit(contact_id):
    contact = get_contact(contact_id)
    values = dict(contact)
    methods = get_contact_methods(contact_id)
    if not methods:
        methods = [{"method_type": "phone", "label": "", "value": ""}]

    if request.method == "POST":
        values, submitted_methods, valid_methods, errors = validate_contact_form(
            request.form
        )
        methods = submitted_methods

        if not errors:
            database = get_db()
            with database:
                database.execute(
                    """
                    UPDATE contacts
                    SET name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (values["name"], contact_id),
                )
                database.execute(
                    "DELETE FROM contact_methods WHERE contact_id = ?",
                    (contact_id,),
                )
                insert_contact_methods(database, contact_id, valid_methods)
            flash(translate("Contact updated successfully."), "success")
            return redirect(url_for("contacts.detail", contact_id=contact_id))

        for error in errors:
            flash(translate(error), "error")

    return render_template(
        "contact_form.html",
        contact=values,
        methods=methods,
        method_types=METHOD_TYPES,
        page_title="Edit contact",
    )


@bp.route("/contacts/<int:contact_id>/delete", methods=("POST",))
def delete(contact_id):
    contact = get_contact(contact_id)
    database = get_db()
    database.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    database.commit()
    flash(translate("{name} was deleted.", name=contact["name"]), "success")
    return redirect(url_for("contacts.index"))

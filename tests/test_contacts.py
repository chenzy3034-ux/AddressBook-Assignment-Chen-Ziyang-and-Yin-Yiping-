import sqlite3

from app import create_app


def contact_form_data(**overrides):
    data = {
        "name": "Ada Lovelace",
        "method_type": ["phone", "email", "address"],
        "method_label": ["Mobile", "Personal", "Home"],
        "method_value": [
            "+44 20 0000 0000",
            "ada@example.com",
            "12 Computing Lane",
        ],
    }
    data.update(overrides)
    return data


def create_contact(client, **overrides):
    return client.post(
        "/contacts/new",
        data=contact_form_data(**overrides),
        follow_redirects=True,
    )


def test_empty_contact_list(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"No contacts yet" in response.data


def test_create_and_view_contact_with_multiple_methods(client, database):
    response = create_contact(
        client,
        method_type=["phone", "phone", "email", "social", "address"],
        method_label=["Mobile", "Work", "Personal", "GitHub", "Home"],
        method_value=[
            "+44 20 0000 0000",
            "+44 20 1111 1111",
            "ada@example.com",
            "@ada",
            "12 Computing Lane",
        ],
    )

    assert response.status_code == 200
    assert b"Contact created successfully." in response.data
    assert b"Phone numbers" in response.data
    assert b"Email addresses" in response.data
    assert b"Social media" in response.data
    assert b"Postal addresses" in response.data
    assert b"+44 20 1111 1111" in response.data
    assert b"@ada" in response.data

    contact = database.execute("SELECT * FROM contacts").fetchone()
    methods = database.execute(
        "SELECT method_type, label, value FROM contact_methods WHERE contact_id = ?",
        (contact["id"],),
    ).fetchall()
    assert contact["name"] == "Ada Lovelace"
    assert len(methods) == 5
    assert [method["method_type"] for method in methods].count("phone") == 2

    list_response = client.get("/")
    assert b"Ada Lovelace" in list_response.data
    assert b"+44 20 0000 0000" in list_response.data


def test_name_and_contact_method_are_required(client, database):
    response = client.post(
        "/contacts/new",
        data={
            "name": "",
            "method_type": ["phone"],
            "method_label": ["Mobile"],
            "method_value": [""],
        },
    )

    assert response.status_code == 200
    assert b"Name is required." in response.data
    assert b"At least one contact method is required." in response.data
    assert database.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0


def test_edit_can_modify_add_and_remove_methods(client, database):
    create_contact(client)
    contact_id = database.execute("SELECT id FROM contacts").fetchone()["id"]

    response = client.post(
        f"/contacts/{contact_id}/edit",
        data=contact_form_data(
            name="Grace Hopper",
            method_type=["phone", "phone", "social"],
            method_label=["Mobile", "Office", "LinkedIn"],
            method_value=["555-0199", "555-0155", "grace-hopper"],
        ),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Contact updated successfully." in response.data
    assert b"Grace Hopper" in response.data
    assert b"555-0155" in response.data
    assert b"grace-hopper" in response.data
    assert b"ada@example.com" not in response.data

    methods = database.execute(
        """
        SELECT method_type, label, value FROM contact_methods
        WHERE contact_id = ? ORDER BY sort_order
        """,
        (contact_id,),
    ).fetchall()
    assert [(method["method_type"], method["value"]) for method in methods] == [
        ("phone", "555-0199"),
        ("phone", "555-0155"),
        ("social", "grace-hopper"),
    ]


def test_delete_contact_cascades_to_methods(client, database):
    create_contact(client)
    contact_id = database.execute("SELECT id FROM contacts").fetchone()["id"]

    response = client.post(
        f"/contacts/{contact_id}/delete", follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Ada Lovelace was deleted." in response.data
    assert b"No contacts yet" in response.data
    assert database.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0
    assert database.execute("SELECT COUNT(*) FROM contact_methods").fetchone()[0] == 0


def test_missing_contact_returns_not_found(client):
    response = client.get("/contacts/999")

    assert response.status_code == 404
    assert b"Page not found" in response.data


def test_toggle_favorite_on_and_off(client, database):
    create_contact(client)
    contact_id = database.execute("SELECT id FROM contacts").fetchone()["id"]

    favorite_response = client.post(
        f"/contacts/{contact_id}/favorite",
        data={"filter": "all"},
        follow_redirects=True,
    )

    assert favorite_response.status_code == 200
    assert b"Ada Lovelace was added to favorites." in favorite_response.data
    assert database.execute(
        "SELECT is_favorite FROM contacts WHERE id = ?", (contact_id,)
    ).fetchone()["is_favorite"] == 1

    unfavorite_response = client.post(
        f"/contacts/{contact_id}/favorite",
        data={"filter": "all"},
        follow_redirects=True,
    )

    assert b"Ada Lovelace was removed from favorites." in unfavorite_response.data
    assert database.execute(
        "SELECT is_favorite FROM contacts WHERE id = ?", (contact_id,)
    ).fetchone()["is_favorite"] == 0


def test_filter_favorite_contacts(client, database):
    create_contact(client)
    create_contact(client, name="Grace Hopper")
    favorite_id = database.execute(
        "SELECT id FROM contacts WHERE name = ?", ("Ada Lovelace",)
    ).fetchone()["id"]
    client.post(f"/contacts/{favorite_id}/favorite")

    response = client.get("/?filter=favorites")

    assert response.status_code == 200
    assert b"Ada Lovelace" in response.data
    assert b"Grace Hopper" not in response.data
    assert b"Favorite contacts" in response.data


def test_favorite_status_persists_between_app_contexts(application):
    from app.db import get_db

    with application.app_context():
        database = get_db()
        cursor = database.execute(
            "INSERT INTO contacts (name, is_favorite) VALUES (?, ?)",
            ("Favorite Contact", 1),
        )
        contact_id = cursor.lastrowid
        database.commit()

    with application.app_context():
        contact = get_db().execute(
            "SELECT is_favorite FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        assert contact["is_favorite"] == 1


def test_contact_methods_persist_between_app_contexts(application):
    from app.db import get_db

    with application.app_context():
        database = get_db()
        cursor = database.execute(
            "INSERT INTO contacts (name) VALUES (?)", ("Persistent Contact",)
        )
        contact_id = cursor.lastrowid
        database.execute(
            """
            INSERT INTO contact_methods (contact_id, method_type, label, value)
            VALUES (?, ?, ?, ?)
            """,
            (contact_id, "phone", "Mobile", "555-0101"),
        )
        database.commit()

    with application.app_context():
        method = get_db().execute(
            "SELECT * FROM contact_methods WHERE contact_id = ?", (contact_id,)
        ).fetchone()
        assert method is not None
        assert method["value"] == "555-0101"


def test_legacy_contact_methods_are_migrated(tmp_path):
    database_path = tmp_path / "legacy.sqlite"
    legacy_database = sqlite3.connect(database_path)
    legacy_database.executescript(
        """
        CREATE TABLE contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO contacts (name, phone, email, address)
        VALUES ('Legacy Contact', '555-0102', 'legacy@example.com', 'Old Street');
        """
    )
    legacy_database.close()

    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "DATABASE": str(database_path),
        }
    )

    with application.app_context():
        from app.db import get_db

        methods = get_db().execute(
            "SELECT method_type, value FROM contact_methods ORDER BY sort_order"
        ).fetchall()
        assert [(method["method_type"], method["value"]) for method in methods] == [
            ("phone", "555-0102"),
            ("email", "legacy@example.com"),
            ("address", "Old Street"),
        ]

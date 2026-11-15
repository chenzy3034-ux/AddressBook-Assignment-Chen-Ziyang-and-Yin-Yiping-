def create_contact(client, **overrides):
    data = {
        "name": "Ada Lovelace",
        "phone": "+44 20 0000 0000",
        "email": "ada@example.com",
        "address": "12 Computing Lane",
    }
    data.update(overrides)
    return client.post("/contacts/new", data=data, follow_redirects=True)


def test_empty_contact_list(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"No contacts yet" in response.data


def test_create_and_view_contact(client, database):
    response = create_contact(client)

    assert response.status_code == 200
    assert b"Contact created successfully." in response.data
    assert b"Ada Lovelace" in response.data
    assert b"ada@example.com" in response.data

    contact = database.execute("SELECT * FROM contacts").fetchone()
    assert contact["name"] == "Ada Lovelace"
    assert contact["phone"] == "+44 20 0000 0000"

    list_response = client.get("/")
    assert b"Ada Lovelace" in list_response.data


def test_name_and_contact_method_are_required(client, database):
    response = client.post(
        "/contacts/new",
        data={"name": "", "phone": "", "email": "", "address": ""},
    )

    assert response.status_code == 200
    assert b"Name is required." in response.data
    assert b"At least one contact method is required." in response.data
    assert database.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0


def test_edit_contact(client, database):
    create_contact(client)
    contact_id = database.execute("SELECT id FROM contacts").fetchone()["id"]

    response = client.post(
        f"/contacts/{contact_id}/edit",
        data={
            "name": "Grace Hopper",
            "phone": "555-0199",
            "email": "grace@example.com",
            "address": "Navy Street",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Contact updated successfully." in response.data
    assert b"Grace Hopper" in response.data
    updated = database.execute(
        "SELECT * FROM contacts WHERE id = ?", (contact_id,)
    ).fetchone()
    assert updated["email"] == "grace@example.com"


def test_delete_contact(client, database):
    create_contact(client)
    contact_id = database.execute("SELECT id FROM contacts").fetchone()["id"]

    response = client.post(
        f"/contacts/{contact_id}/delete", follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Ada Lovelace was deleted." in response.data
    assert b"No contacts yet" in response.data
    assert database.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0


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
    create_contact(
        client,
        name="Grace Hopper",
        phone="555-0199",
        email="grace@example.com",
    )
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
            "INSERT INTO contacts (name, phone, is_favorite) VALUES (?, ?, ?)",
            ("Favorite Contact", "555-0133", 1),
        )
        contact_id = cursor.lastrowid
        database.commit()

    with application.app_context():
        contact = get_db().execute(
            "SELECT is_favorite FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        assert contact["is_favorite"] == 1


def test_database_persists_between_app_contexts(application):
    from app.db import get_db

    with application.app_context():
        database = get_db()
        database.execute(
            "INSERT INTO contacts (name, phone) VALUES (?, ?)",
            ("Persistent Contact", "555-0101"),
        )
        database.commit()

    with application.app_context():
        contact = get_db().execute(
            "SELECT * FROM contacts WHERE name = ?", ("Persistent Contact",)
        ).fetchone()
        assert contact is not None
        assert contact["phone"] == "555-0101"

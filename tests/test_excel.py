from io import BytesIO
from pathlib import Path

from openpyxl import Workbook, load_workbook


def seed_contacts(database):
    first = database.execute(
        "INSERT INTO contacts (name, is_favorite) VALUES (?, ?)",
        ("Ada Lovelace", 1),
    )
    database.executemany(
        """
        INSERT INTO contact_methods
            (contact_id, method_type, label, value, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (first.lastrowid, "phone", "Mobile", "+44 20 0000 0000", 0),
            (first.lastrowid, "phone", "Work", "+44 20 1111 1111", 1),
            (first.lastrowid, "email", "Personal", "ada@example.com", 2),
            (first.lastrowid, "social", "GitHub", "@ada", 3),
            (first.lastrowid, "address", "Home", "12 Computing Lane", 4),
        ],
    )
    second = database.execute(
        "INSERT INTO contacts (name, is_favorite) VALUES (?, ?)",
        ("Grace Hopper", 0),
    )
    database.execute(
        """
        INSERT INTO contact_methods
            (contact_id, method_type, label, value, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        (second.lastrowid, "email", "Work", "grace@example.com", 0),
    )
    database.commit()


def database_snapshot(database):
    contacts = database.execute(
        "SELECT name, is_favorite FROM contacts ORDER BY name"
    ).fetchall()
    snapshot = []
    for contact in contacts:
        contact_id = database.execute(
            "SELECT id FROM contacts WHERE name = ?", (contact["name"],)
        ).fetchone()["id"]
        methods = database.execute(
            """
            SELECT method_type, label, value FROM contact_methods
            WHERE contact_id = ? ORDER BY sort_order, id
            """,
            (contact_id,),
        ).fetchall()
        snapshot.append(
            (
                contact["name"],
                contact["is_favorite"],
                [tuple(method) for method in methods],
            )
        )
    return snapshot


def workbook_bytes(rows):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Contacts"
    for row in rows:
        worksheet.append(row)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def test_contact_list_has_excel_actions(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Import" in response.data
    assert b"Export contacts" in response.data
    assert b"Download example" in response.data


def test_example_workbook_is_available_and_compatible(client, database):
    response = client.get(
        "/static/examples/address_book_import_example.xlsx"
    )

    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.data), read_only=True, data_only=True)
    worksheet = workbook["Contacts"]
    headers = [cell.value for cell in worksheet[1]]
    assert headers[:4] == ["Name", "Favorite", "Phone 1 Label", "Phone 1"]
    assert worksheet["A2"].value == "Ada Lovelace"
    workbook.close()
    assert Path("app/static/examples/address_book_import_example.xlsx").is_file()

    import_response = client.post(
        "/contacts/import",
        data={"file": (BytesIO(response.data), "example.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Imported 2 contact(s)." in import_response.data
    assert database.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 2


def test_export_contains_clear_headers_and_all_methods(client, database):
    seed_contacts(database)

    response = client.get("/contacts/export")

    assert response.status_code == 200
    assert response.mimetype == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(BytesIO(response.data), read_only=True, data_only=True)
    worksheet = workbook["Contacts"]
    rows = list(worksheet.iter_rows(values_only=True))
    headers = list(rows[0])
    ada = dict(zip(headers, rows[1]))

    assert headers[:2] == ["Name", "Favorite"]
    assert "Phone 1" in headers
    assert "Phone 2" in headers
    assert "Email 1" in headers
    assert "Social 1" in headers
    assert "Address 1" in headers
    assert ada["Name"] == "Ada Lovelace"
    assert ada["Favorite"] == "Yes"
    assert ada["Phone 1"] == "+44 20 0000 0000"
    assert ada["Phone 2"] == "+44 20 1111 1111"
    assert ada["Social 1"] == "@ada"
    workbook.close()


def test_export_clear_and_import_round_trip(client, database):
    seed_contacts(database)
    expected = database_snapshot(database)
    exported = client.get("/contacts/export").data

    database.execute("DELETE FROM contacts")
    database.commit()
    assert database.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0

    response = client.post(
        "/contacts/import",
        data={"file": (BytesIO(exported), "contacts.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Imported 2 contact(s)." in response.data
    assert database_snapshot(database) == expected

    detail = client.get(
        f"/contacts/{database.execute('SELECT id FROM contacts WHERE name = ?', ('Ada Lovelace',)).fetchone()['id']}"
    )
    assert b"+44 20 1111 1111" in detail.data
    assert b"@ada" in detail.data


def test_import_skips_database_and_workbook_duplicates(client, database):
    workbook = workbook_bytes(
        [
            ["Name", "Favorite", "Phone 1 Label", "Phone 1"],
            ["Duplicate Contact", "No", "Mobile", "555-0101"],
            ["Duplicate Contact", "Yes", "Other label", "555-0101"],
        ]
    )

    first_response = client.post(
        "/contacts/import",
        data={"file": (BytesIO(workbook.getvalue()), "duplicates.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    second_response = client.post(
        "/contacts/import",
        data={"file": (BytesIO(workbook.getvalue()), "duplicates.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert b"Imported 1 contact(s)." in first_response.data
    assert b"Skipped 1 duplicate(s)." in first_response.data
    assert b"Imported 0 contact(s)." in second_response.data
    assert b"Skipped 2 duplicate(s)." in second_response.data
    assert database.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 1


def test_import_handles_empty_cells_and_invalid_rows(client, database):
    workbook = workbook_bytes(
        [
            [
                "Name",
                "Favorite",
                "Phone 1 Label",
                "Phone 1",
                "Email 1 Label",
                "Email 1",
            ],
            ["Valid Contact", "", "", "555-0103", None, None],
            ["", "No", "Mobile", "555-0104", None, None],
            ["No Methods", "No", None, None, None, None],
            [None, None, None, None, None, None],
        ]
    )

    response = client.post(
        "/contacts/import",
        data={"file": (workbook, "mixed.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Imported 1 contact(s)." in response.data
    assert b"Ignored 2 invalid row(s)." in response.data
    contact = database.execute("SELECT * FROM contacts").fetchone()
    assert contact["name"] == "Valid Contact"
    assert contact["is_favorite"] == 0


def test_import_rejects_invalid_files(client, database):
    invalid_xlsx = client.post(
        "/contacts/import",
        data={"file": (BytesIO(b"not a workbook"), "broken.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    wrong_extension = client.post(
        "/contacts/import",
        data={"file": (BytesIO(b"text"), "contacts.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert invalid_xlsx.status_code == 200
    assert b"could not be imported" in invalid_xlsx.data
    assert b"Only .xlsx files are supported." in wrong_extension.data
    assert database.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0

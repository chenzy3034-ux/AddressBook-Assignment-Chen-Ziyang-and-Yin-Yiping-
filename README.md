# Address Book Application

A small Flask application for managing contacts. The first development phase
supports creating, viewing, editing, and deleting contacts with persistent
SQLite storage.

## Features

- View all contacts in a simple web interface
- Add a contact with a name, phone number, email address, and postal address
- View an individual contact
- Edit an existing contact
- Delete a contact after confirmation
- Keep data in a local SQLite database between application restarts

Favorite contacts and Excel import/export are intentionally excluded from this
phase.

## Project Structure

```text
.
|-- app/
|   |-- static/
|   |   `-- styles.css
|   |-- templates/
|   |   |-- base.html
|   |   |-- contact_detail.html
|   |   |-- contact_form.html
|   |   |-- contact_list.html
|   |   `-- not_found.html
|   |-- __init__.py
|   |-- contacts.py
|   |-- db.py
|   `-- schema.sql
|-- tests/
|   |-- conftest.py
|   `-- test_contacts.py
|-- .gitignore
|-- requirements.txt
`-- run.py
```

## Requirements

- Python 3.11 or newer
- pip

## Setup and Run

Create and activate a virtual environment on macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies and start the application:

```bash
python -m pip install -r requirements.txt
python run.py
```

Open <http://127.0.0.1:5055> in a browser. The application creates the local
database at `instance/address_book.sqlite` automatically on first startup.

## Run Tests

```bash
python -m pytest
```

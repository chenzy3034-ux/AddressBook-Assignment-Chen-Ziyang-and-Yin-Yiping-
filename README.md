# Address Book Application

A small Flask application for managing contacts. The first development phase
supports creating, viewing, editing, and deleting contacts with persistent
SQLite storage.

See the [project coding standards](CODE_STANDARDS.md) for implementation,
testing, and Git collaboration conventions.

## Features

- View all contacts in a simple web interface
- Search contacts by name, contact details, or labels
- Add multiple phone numbers, email addresses, social accounts, and postal addresses
- View an individual contact
- Edit an existing contact
- Delete a contact after confirmation
- Keep data in a local SQLite database between application restarts
- Import and export complete contact records as Excel workbooks

Excel workbooks preserve favorite status and all numbered contact methods.

## Project Structure

```text
.
|-- app/
|   |-- static/
|   |   |-- examples/
|   |   |   `-- address_book_import_example.xlsx
|   |   |-- contact_methods.js
|   |   |-- favicon.svg
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
|   |-- excel.py
|   `-- schema.sql
|-- tests/
|   |-- conftest.py
|   |-- test_contacts.py
|   `-- test_excel.py
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

## Excel Workbook Format

The `Contacts` worksheet uses one row per contact. `Name` and `Favorite` are
required columns. Favorite values accept `Yes`, `No`, `True`, `False`, `1`, or
`0`.

Contact methods use numbered pairs of columns:

- `Phone 1 Label`, `Phone 1`, `Phone 2 Label`, `Phone 2`, and so on
- `Email 1 Label`, `Email 1`, `Email 2 Label`, `Email 2`, and so on
- `Social 1 Label`, `Social 1`, `Social 2 Label`, `Social 2`, and so on
- `Address 1 Label`, `Address 1`, `Address 2 Label`, `Address 2`, and so on

Empty method cells are ignored. Import requires a name and at least one contact
method per row. A row is treated as a duplicate when its normalized name and
complete set of method types and values match an existing or earlier imported
contact. Duplicate rows are skipped rather than merged or inserted again.

## Server Deployment

The shared server exposes the application at
<https://47.117.170.115/address-book/>. Visitors enter a public address
book without a password. They share the same contacts and can view, edit,
or delete them. Use sample data only. Nginx forwards this HTTPS path to the dedicated
`web-address-book.service` on `127.0.0.1:3002`. The application uses a
separate session cookie and checks a CSRF token on every POST.

- Release: `/opt/websites/address-book/current`
- Persistent SQLite: `/var/lib/web-address-book/address_book.sqlite`
- Server-only settings: `/etc/web-address-book/environment`
- Nginx: `/etc/nginx/calculator-sites.d/address-book.conf` and
  `/etc/nginx/conf.d/address-book-limits.conf`

`deploy/install.sh` performs first installation from a verified release
archive. It validates the Nginx configuration, public HTTPS access, and the existing sites. It leaves
SQLite outside the release.

To withdraw the first release, remove the two Address Book Nginx files,
run `nginx -t && systemctl reload nginx`, then run
`systemctl disable --now web-address-book`. Retain the database and
settings for recovery. For later releases, switch `current` back to a
known working release, restart only `web-address-book`, and check the
`/address-book/health` endpoint.

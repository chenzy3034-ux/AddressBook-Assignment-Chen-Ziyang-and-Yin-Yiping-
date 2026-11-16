import re
from collections import defaultdict
from datetime import date, datetime
from io import BytesIO
from zipfile import ZipFile

from flask import Blueprint, flash, redirect, request, send_file, url_for
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .db import get_db
from .i18n import translate


bp = Blueprint("excel", __name__)

METHOD_EXPORT_NAMES = {
    "phone": "Phone",
    "email": "Email",
    "social": "Social",
    "address": "Address",
}
METHOD_IMPORT_NAMES = {
    export_name.lower(): method_type
    for method_type, export_name in METHOD_EXPORT_NAMES.items()
}
METHOD_HEADER_PATTERN = re.compile(
    r"^(Phone|Email|Social|Address) ([1-9]\d*)( Label)?$", re.IGNORECASE
)
MAX_IMPORT_ROWS = 5000
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_EXPANDED_SIZE = 32 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 256


def normalize_text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_fingerprint_value(value):
    return " ".join(value.casefold().split())


def contact_fingerprint(name, methods):
    normalized_methods = sorted(
        (
            method["method_type"],
            normalize_fingerprint_value(method["value"]),
        )
        for method in methods
    )
    return normalize_fingerprint_value(name), tuple(normalized_methods)


def get_existing_fingerprints(database):
    contacts = database.execute("SELECT id, name FROM contacts").fetchall()
    methods = database.execute(
        """
        SELECT contact_id, method_type, value
        FROM contact_methods
        ORDER BY contact_id, sort_order, id
        """
    ).fetchall()
    methods_by_contact = defaultdict(list)
    for method in methods:
        methods_by_contact[method["contact_id"]].append(method)

    return {
        contact_fingerprint(contact["name"], methods_by_contact[contact["id"]])
        for contact in contacts
    }


def write_text_cell(worksheet, row, column, value):
    cell = worksheet.cell(row=row, column=column, value=value)
    if isinstance(value, str):
        cell.data_type = "s"
    return cell


def build_export_workbook(database):
    contacts = database.execute(
        "SELECT id, name, is_favorite FROM contacts ORDER BY name COLLATE NOCASE, id"
    ).fetchall()
    methods = database.execute(
        """
        SELECT contact_id, method_type, label, value
        FROM contact_methods
        ORDER BY contact_id, method_type, sort_order, id
        """
    ).fetchall()
    methods_by_contact = defaultdict(lambda: defaultdict(list))
    max_counts = {method_type: 1 for method_type in METHOD_EXPORT_NAMES}

    for method in methods:
        method_list = methods_by_contact[method["contact_id"]][method["method_type"]]
        method_list.append(method)
        max_counts[method["method_type"]] = max(
            max_counts[method["method_type"]], len(method_list)
        )

    headers = ["Name", "Favorite"]
    method_columns = []
    for method_type, export_name in METHOD_EXPORT_NAMES.items():
        for index in range(1, max_counts[method_type] + 1):
            headers.extend([f"{export_name} {index} Label", f"{export_name} {index}"])
            method_columns.append((method_type, index - 1))

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Contacts"
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"

    for column, header in enumerate(headers, start=1):
        cell = write_text_cell(worksheet, 1, column, header)
        cell.fill = PatternFill("solid", fgColor="3157D5")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_index, contact in enumerate(contacts, start=2):
        write_text_cell(worksheet, row_index, 1, contact["name"])
        write_text_cell(
            worksheet, row_index, 2, "Yes" if contact["is_favorite"] else "No"
        )
        column = 3
        for method_type, method_index in method_columns:
            available_methods = methods_by_contact[contact["id"]][method_type]
            method = (
                available_methods[method_index]
                if method_index < len(available_methods)
                else None
            )
            write_text_cell(
                worksheet, row_index, column, method["label"] if method else ""
            )
            write_text_cell(
                worksheet, row_index, column + 1, method["value"] if method else ""
            )
            column += 2

    worksheet.row_dimensions[1].height = 24
    for column, header in enumerate(headers, start=1):
        width = max(14, min(34, len(header) + 4))
        if header == "Name":
            width = 24
        worksheet.column_dimensions[get_column_letter(column)].width = width

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def parse_favorite(value):
    normalized = normalize_text(value).casefold()
    if normalized in ("yes", "true", "1", "favorite"):
        return 1
    if normalized in ("", "no", "false", "0", "not favorite"):
        return 0
    raise ValueError(translate("Favorite must be Yes or No."))


def parse_import_workbook(file_bytes):
    with ZipFile(BytesIO(file_bytes)) as archive:
        entries = archive.infolist()
        if (
            len(entries) > MAX_ARCHIVE_ENTRIES
            or sum(entry.file_size for entry in entries) > MAX_EXPANDED_SIZE
        ):
            raise ValueError(translate("The workbook is too large after decompression."))

    workbook = load_workbook(
        filename=BytesIO(file_bytes), read_only=True, data_only=True, keep_links=False
    )
    worksheet = workbook["Contacts"] if "Contacts" in workbook.sheetnames else workbook.active

    row_iterator = worksheet.iter_rows()
    header_cells = next(row_iterator, None)
    if header_cells is None:
        raise ValueError(translate("The workbook is empty."))
    header_values = [normalize_text(cell.value) for cell in header_cells]
    if len(header_values) != len(set(header_values)):
        raise ValueError(translate("The workbook contains duplicate column headers."))

    header_indexes = {header: index for index, header in enumerate(header_values)}
    if "Name" not in header_indexes or "Favorite" not in header_indexes:
        raise ValueError(translate("The workbook must contain Name and Favorite columns."))

    method_columns = defaultdict(dict)
    unknown_headers = []
    for index, header in enumerate(header_values):
        if header in ("Name", "Favorite"):
            continue
        match = METHOD_HEADER_PATTERN.fullmatch(header)
        if match is None:
            if header:
                unknown_headers.append(header)
            continue
        method_type = METHOD_IMPORT_NAMES[match.group(1).casefold()]
        method_number = int(match.group(2))
        field = "label" if match.group(3) else "value"
        method_columns[(method_type, method_number)][field] = index

    if unknown_headers:
        raise ValueError(
            translate("Unsupported column header: {header}.", header=unknown_headers[0])
        )
    if not any("value" in columns for columns in method_columns.values()):
        raise ValueError(translate("The workbook must contain at least one contact method column."))

    contacts = []
    invalid_rows = []
    for row_number, cells in enumerate(row_iterator, start=2):
        if row_number - 1 > MAX_IMPORT_ROWS:
            raise ValueError(
                translate("The workbook cannot contain more than {count} rows.", count=MAX_IMPORT_ROWS)
            )
        values = [cell.value for cell in cells]
        if not any(normalize_text(value) for value in values):
            continue

        name = normalize_text(values[header_indexes["Name"]])
        try:
            is_favorite = parse_favorite(values[header_indexes["Favorite"]])
        except ValueError as error:
            invalid_rows.append(translate("Row {row}: {reason}", row=row_number, reason=error))
            continue

        methods = []
        method_type_order = {
            method_type: index
            for index, method_type in enumerate(METHOD_EXPORT_NAMES)
        }
        ordered_method_columns = sorted(
            method_columns.items(),
            key=lambda item: (method_type_order[item[0][0]], item[0][1]),
        )
        for sort_order, ((method_type, method_number), columns) in enumerate(
            ordered_method_columns
        ):
            value_index = columns.get("value")
            value = normalize_text(values[value_index]) if value_index is not None else ""
            if not value:
                continue
            label_index = columns.get("label")
            label = normalize_text(values[label_index]) if label_index is not None else ""
            methods.append(
                {
                    "method_type": method_type,
                    "label": label,
                    "value": value,
                    "sort_order": sort_order,
                }
            )

        if not name:
            invalid_rows.append(
                translate("Row {row}: {reason}", row=row_number, reason=translate("Name is required."))
            )
        elif not methods:
            invalid_rows.append(
                translate(
                    "Row {row}: {reason}",
                    row=row_number,
                    reason=translate("At least one contact method is required."),
                )
            )
        else:
            contacts.append(
                {"name": name, "is_favorite": is_favorite, "methods": methods}
            )

    workbook.close()
    return contacts, invalid_rows


def import_contacts(database, contacts):
    known_fingerprints = get_existing_fingerprints(database)
    contacts_to_import = []
    duplicate_count = 0

    for contact in contacts:
        fingerprint = contact_fingerprint(contact["name"], contact["methods"])
        if fingerprint in known_fingerprints:
            duplicate_count += 1
            continue
        known_fingerprints.add(fingerprint)
        contacts_to_import.append(contact)

    with database:
        for contact in contacts_to_import:
            cursor = database.execute(
                "INSERT INTO contacts (name, is_favorite) VALUES (?, ?)",
                (contact["name"], contact["is_favorite"]),
            )
            database.executemany(
                """
                INSERT INTO contact_methods
                    (contact_id, method_type, label, value, sort_order)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        cursor.lastrowid,
                        method["method_type"],
                        method["label"],
                        method["value"],
                        method["sort_order"],
                    )
                    for method in contact["methods"]
                ],
            )

    return len(contacts_to_import), duplicate_count


@bp.route("/contacts/export")
def export_contacts():
    workbook = build_export_workbook(get_db())
    return send_file(
        workbook,
        as_attachment=True,
        download_name="address_book_contacts.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/contacts/import", methods=("POST",))
def import_contacts_route():
    uploaded_file = request.files.get("file")
    if uploaded_file is None or not uploaded_file.filename:
        flash(translate("Choose an Excel file to import."), "error")
        return redirect(url_for("contacts.index"))
    if not uploaded_file.filename.lower().endswith(".xlsx"):
        flash(translate("Only .xlsx files are supported."), "error")
        return redirect(url_for("contacts.index"))

    file_bytes = uploaded_file.read(MAX_FILE_SIZE + 1)
    if len(file_bytes) > MAX_FILE_SIZE:
        flash(translate("The Excel file must be 5 MB or smaller."), "error")
        return redirect(url_for("contacts.index"))

    try:
        contacts, invalid_rows = parse_import_workbook(file_bytes)
        imported_count, duplicate_count = import_contacts(get_db(), contacts)
    except ValueError as error:
        flash(translate("The Excel file could not be imported: {reason}", reason=error), "error")
        return redirect(url_for("contacts.index"))
    except Exception:
        flash(translate("The Excel file could not be imported."), "error")
        return redirect(url_for("contacts.index"))

    flash(
        translate(
            "Imported {imported} contact(s). "
            "Skipped {duplicates} duplicate(s). "
            "Ignored {invalid} invalid row(s).",
            imported=imported_count,
            duplicates=duplicate_count,
            invalid=len(invalid_rows),
        ),
        "success",
    )
    if invalid_rows:
        flash(invalid_rows[0], "error")
    return redirect(url_for("contacts.index"))

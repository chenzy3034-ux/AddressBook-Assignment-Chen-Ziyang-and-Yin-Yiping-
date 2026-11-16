# Address Book coding standards

## Python and SQLite

- Follow [PEP 8](https://peps.python.org/pep-0008/) and match the surrounding code. Use four spaces for indentation, `snake_case` for functions and variables, and uppercase names for constants.
- Keep contact routes in `app/contacts.py`, workbook rules in `app/excel.py`, and SQLite setup in `app/db.py` and `app/schema.sql`.
- Bind user input as SQL parameters. Group related writes in a transaction so an interrupted edit or import cannot leave partial contact records.
- Validate form values and workbooks on the server. Keep workbook headings compatible with the sample in `app/static/examples/`.

## Templates, styles, and localization

- Generate route and asset URLs with Flask's `url_for()` so the application also works at the deployed subpath.
- Use shared Jinja templates and CSS for repeated patterns. Keep scripts in static files and preserve form labels, keyboard access, and reduced-motion support.
- Add new interface messages to the English and Chinese translation flow in `app/i18n.py`. Preserve the user's original contact data and the shared Excel format in both languages.

## Verification and Git

- Run `python -m pytest -q` before requesting review. Check contact editing, favorites, and Excel import/export when a change touches those flows.
- Make each commit describe a coherent change. Use the repository's existing prefixes such as `feat:`, `fix:`, and `docs:`.
- Open a pull request from a topic branch and describe the change and its verification. Keep SQLite databases, virtual environments, and server credentials out of Git.

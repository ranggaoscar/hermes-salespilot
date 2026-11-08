"""Authorized CSV import. Parses and validates. Does not contact anyone."""

from __future__ import annotations

import csv
import io
from typing import Any

FIELDS = ("company", "contact_name", "email", "phone", "segment", "notes")


def _formula(value: str) -> bool:
    return bool(value) and value[0] in "=+@"


def parse_csv(csv_text: str, mapping: dict[str, str]) -> dict[str, Any]:
    if not str(csv_text or "").strip():
        return {"ok": False, "code": "empty_csv", "error": "CSV text is empty."}
    if not isinstance(mapping, dict) or not mapping:
        return {"ok": False, "code": "missing_mapping", "error": "Column mapping is required."}
    unknown = sorted(set(mapping.values()) - set(FIELDS))
    if unknown:
        return {"ok": False, "code": "bad_mapping", "error": "Unknown target fields: " + ", ".join(unknown)}
    if "company" not in mapping.values():
        return {"ok": False, "code": "missing_company_column", "error": "Mapping must include a company column."}
    handle = io.StringIO(csv_text.lstrip("\ufeff"))
    reader = csv.DictReader(handle)
    headers = reader.fieldnames or []
    if not headers or any(not (name or "").strip() for name in headers):
        return {"ok": False, "code": "bad_header", "error": "CSV needs a header row."}
    missing_headers = sorted(set(mapping) - set(headers))
    if missing_headers:
        return {
            "ok": False,
            "code": "mapping_header_mismatch",
            "error": "Mapping keys are not CSV headers: " + ", ".join(missing_headers),
        }
    rows = []
    errors = []
    seen: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(reader, start=2):
        mapped = {field: "" for field in FIELDS}
        for header, field in mapping.items():
            mapped[field] = str((raw or {}).get(header) or "").strip()
        if not mapped["company"]:
            errors.append({"row": index, "code": "missing_company", "company": ""})
            continue
        if any(_formula(mapped[field]) for field in ("company", "contact_name", "email", "notes")):
            errors.append({"row": index, "code": "spreadsheet_formula", "company": mapped["company"][:40]})
            continue
        key = (mapped["company"].casefold(), mapped["email"].casefold(), mapped["phone"])
        if key in seen:
            errors.append({"row": index, "code": "duplicate_in_file", "company": mapped["company"]})
            continue
        seen.add(key)
        rows.append({"row_number": index, **mapped})
    return {"ok": True, "rows": rows, "errors": errors, "header": list(headers)}

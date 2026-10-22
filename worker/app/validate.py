"""Safe, read-only inspection of an uploaded .xlsx.

Never executes macros, never follows external links, never logs cell contents.
"""
import io
import zipfile
from dataclasses import dataclass

import openpyxl

MAX_ZIP_ENTRIES = 2000
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


class Rejected(Exception):
    """File refused. `message` is safe to show to the user."""

    def __init__(self, code: str, message: str):
        super().__init__(code)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Inspection:
    sheet_count: int
    hidden_sheets: int
    has_external_links: bool


def inspect_xlsx(data: bytes, max_bytes: int) -> Inspection:
    if len(data) == 0:
        raise Rejected("empty", "The file is empty.")
    if len(data) > max_bytes:
        raise Rejected("too_large", f"The file is larger than {max_bytes // (1024 * 1024)} MB.")
    if not data.startswith(b"PK\x03\x04"):
        raise Rejected("not_xlsx", "This is not a valid .xlsx file.")

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise Rejected("corrupt", "The file is corrupted and cannot be opened.")

    infos = zf.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        raise Rejected("unsafe_archive", "The file structure is too complex to process safely.")
    total = sum(i.file_size for i in infos)
    if total > MAX_UNCOMPRESSED_BYTES or total / len(data) > MAX_COMPRESSION_RATIO:
        raise Rejected("unsafe_archive", "The file expands to an unsafe size and was refused.")

    names = {i.filename.lower() for i in infos}
    if any(n.endswith("vbaproject.bin") for n in names):
        raise Rejected("macros", "Files with macros are not supported. Save a copy without macros (.xlsx).")
    if "[content_types].xml" not in names or "xl/workbook.xml" not in names:
        raise Rejected("not_xlsx", "This is not a valid Excel workbook.")

    has_external = any(n.startswith("xl/externallinks/") for n in names)

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=False, keep_vba=False)
        try:
            sheets = wb.worksheets
            hidden = sum(1 for ws in sheets if ws.sheet_state != "visible")
            count = len(sheets)
        finally:
            wb.close()
    except Exception:
        raise Rejected("unreadable", "The workbook could not be read. It may be damaged or password-protected.")

    if count == 0:
        raise Rejected("no_sheets", "The workbook has no sheets.")

    return Inspection(sheet_count=count, hidden_sheets=hidden, has_external_links=has_external)

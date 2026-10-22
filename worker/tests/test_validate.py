import io
import zipfile

import openpyxl
import pytest

from app.validate import Rejected, inspect_xlsx

MAX = 10 * 1024 * 1024


def make_xlsx(sheets=("Sales",), hidden=()):
    wb = openpyxl.Workbook()
    wb.active.title = sheets[0]
    for name in sheets[1:]:
        wb.create_sheet(name)
    for name in hidden:
        wb[name].sheet_state = "hidden"
    wb[sheets[0]].append(["date", "amount"])
    wb[sheets[0]].append(["2026-01-01", 10])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_valid_workbook_counts_sheets():
    info = inspect_xlsx(make_xlsx(("A", "B", "C"), hidden=("C",)), MAX)
    assert info.sheet_count == 3
    assert info.hidden_sheets == 1
    assert info.has_external_links is False


def test_empty_file_rejected():
    with pytest.raises(Rejected) as e:
        inspect_xlsx(b"", MAX)
    assert e.value.code == "empty"


def test_too_large_rejected():
    with pytest.raises(Rejected) as e:
        inspect_xlsx(make_xlsx(), 100)
    assert e.value.code == "too_large"


def test_not_a_zip_rejected():
    with pytest.raises(Rejected) as e:
        inspect_xlsx(b"hello world, definitely not excel", MAX)
    assert e.value.code == "not_xlsx"


def test_corrupt_zip_rejected():
    data = make_xlsx()
    with pytest.raises(Rejected) as e:
        inspect_xlsx(data[: len(data) // 2], MAX)
    assert e.value.code in {"corrupt", "unreadable"}


def test_macros_rejected():
    src = zipfile.ZipFile(io.BytesIO(make_xlsx()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            out.writestr(item, src.read(item.filename))
        out.writestr("xl/vbaProject.bin", b"fake")
    with pytest.raises(Rejected) as e:
        inspect_xlsx(buf.getvalue(), MAX)
    assert e.value.code == "macros"


def test_zip_that_is_not_excel_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", "hi")
    with pytest.raises(Rejected) as e:
        inspect_xlsx(buf.getvalue(), MAX)
    assert e.value.code == "not_xlsx"


def test_zip_bomb_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<x/>")
        z.writestr("xl/workbook.xml", "<x/>")
        z.writestr("xl/worksheets/sheet1.xml", b"0" * (60 * 1024 * 1024))
    with pytest.raises(Rejected) as e:
        inspect_xlsx(buf.getvalue(), MAX)
    assert e.value.code == "unsafe_archive"

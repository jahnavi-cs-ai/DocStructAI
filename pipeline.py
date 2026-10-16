"""Hybrid PDF table extraction with page provenance and conservative validation.

Native table extraction is preferred. OCR is used for pages without usable text.
No financial number is modified by AI; ambiguous fields are flagged.
"""
from __future__ import annotations
import io
import re
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import fitz
import pdfplumber
import pandas as pd


@dataclass
class ExtractedTable:
    headers: list[str]
    rows: list[list[str]]
    pages: list[int] = field(default_factory=list)
    method: str = "native"
    name: str = ""


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", clean(value).lower())


def normalize_header(raw: list[Any]) -> list[str]:
    names, seen = [], Counter()
    for i, entry in enumerate(raw):
        name = clean(entry) or f"Column_{i+1}"
        seen[name.lower()] += 1
        if seen[name.lower()] > 1:
            name += f"_{seen[name.lower()]}"
        names.append(name)
    return names


def is_repeat_header(row: list[str], headers: list[str]) -> bool:
    if len(row) != len(headers):
        return False
    return sum(normalize(a) == normalize(b) for a, b in zip(row, headers)) >= max(2, int(len(headers) * 0.75))


def header_similarity(a: list[str], b: list[str]) -> float:
    if len(a) != len(b):
        return 0
    return sum(SequenceMatcher(None, normalize(x), normalize(y)).ratio() for x, y in zip(a, b)) / max(len(a), 1)


def numeric(s: str) -> float | None:
    s = clean(s).replace(",", "").replace("₹", "").replace("$", "")
    if re.fullmatch(r"\(?-?\d+(\.\d+)?\)?", s):
        return float("-" + s[1:-1] if s.startswith("(") else s)
    return None


def likely_total(row: list[str]) -> bool:
    return any(re.search(r"\b(grand total|subtotal|total amount|total)\b", x, re.I) for x in row[:min(3, len(row))])


def parse_grid(raw: list[list[Any]], page: int, method: str) -> ExtractedTable | None:
    cells = [[clean(x) for x in row] for row in raw if row]
    if len(cells) < 2:
        return None
    width = max(Counter(len(r) for r in cells).items(), key=lambda x: x[1])[0]
    if width < 2:
        return None
    cells = [(r + [""] * width)[:width] for r in cells]
    cells = [r for r in cells if any(r)]
    if len(cells) < 2:
        return None
    headers = normalize_header(cells[0])
    data = [r for r in cells[1:] if not is_repeat_header(r, headers)]
    return ExtractedTable(headers, data, [page], method)


def scan_page(page: fitz.Page, page_number: int) -> tuple[list[ExtractedTable], list[str]]:
    """OCR reconstructs rows from TSV word bounding boxes and wide gaps.

    Works best with bordered tables; unusually complex scans require review.
    """
    warnings = []
    try:
        import pytesseract
        from PIL import Image
        import pandas as pd
    except ImportError:
        return [], [f"Page {page_number}: OCR dependencies missing"]
    pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    try:
        data = pytesseract.image_to_data(img, config="--psm 6", output_type=pytesseract.Output.DATAFRAME)
    except Exception as exc:
        return [], [f"Page {page_number}: Tesseract unavailable ({exc})"]
    data = data.dropna(subset=["text"])
    data = data[data.conf >= 20].copy()
    if data.empty:
        return [], [f"Page {page_number}: no confident OCR words"]
    # For fully bordered scans, detect ruling lines and OCR individual cells.
    # This avoids Tesseract treating vertical borders as text.
    try:
        import cv2
        import numpy as np
        gray = np.array(img.convert("L"))
        binary = cv2.threshold(gray, 190, 255, cv2.THRESH_BINARY_INV)[1]
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(35, img.height//16))))
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(45, img.width//16), 1)))
        def runs(proj, cut):
            ids = np.flatnonzero(proj > cut)
            groups = []
            for pos in ids:
                if not groups or pos > groups[-1][-1]+1:
                    groups.append([int(pos)])
                else:
                    groups[-1].append(int(pos))
            return [int(sum(g)/len(g)) for g in groups if len(g)>=2]
        xs = runs((vertical > 0).sum(axis=0), int(img.height*0.22))
        ys = runs((horizontal > 0).sum(axis=1), int(img.width*0.22))
        if len(xs)>=3 and len(ys)>=3 and len(xs)<=41:
            grid = []
            for y0,y1 in zip(ys[:-1],ys[1:]):
                row=[]
                for j,(x0,x1) in enumerate(zip(xs[:-1],xs[1:])):
                    crop=img.crop((x0+9,y0+9,x1-9,y1-9))
                    row.append(clean(pytesseract.image_to_string(crop,config="--psm 7")))
                grid.append(row)
            table=parse_grid(grid,page_number,"ocr-grid")
            if table and len(table.rows)>=1:
                return [table],warnings
    except Exception as exc:
        warnings.append(f"Page {page_number}: grid recognition unavailable ({exc})")
    # Reconstruct lines using block/paragraph/line IDs; split on large horizontal gaps.
    groups = []
    for _, words in data.groupby(["block_num", "par_num", "line_num"], sort=False):
        words = words.sort_values("left")
        toks = [(int(r.left), int(r.left+r.width), clean(r.text)) for r in words.itertuples() if clean(r.text)]
        if len(toks) < 2:
            continue
        groups.append(toks)
    if not groups:
        return [], [f"Page {page_number}: insufficient OCR tabular lines"]
    # Cluster word x-left positions into stable column anchors; safeguard text columns.
    xpoints = sorted(x for line in groups for x, _, _ in line)
    anchors = []
    threshold = max(24, int(img.width * 0.013))
    for x in xpoints:
        if not anchors or x - anchors[-1][-1] > threshold:
            anchors.append([x])
        else:
            anchors[-1].append(x)
    centers = [sum(a)/len(a) for a in anchors]
    if not (2 <= len(centers) <= 40):
        return [], [f"Page {page_number}: OCR column geometry ambiguous"]
    rows = []
    for line in groups:
        row = [""] * len(centers)
        for x, _, text in line:
            col = min(range(len(centers)), key=lambda j: abs(centers[j] - x))
            row[col] = (row[col] + " " + text).strip()
        if sum(bool(v) for v in row) >= 2:
            rows.append(row)
    # Columns with only one word are often artifacts from OCR. Eliminate near-empty positions.
    keep = [i for i in range(len(centers)) if sum(bool(r[i]) for r in rows) >= 2]
    rows = [[r[i] for i in keep] for r in rows]
    table = parse_grid(rows, page_number, "ocr") if rows else None
    warnings.append(f"Page {page_number}: OCR geometry is approximate; visually review columns")
    return ([table] if table else []), warnings


def extract_tables(pdf_bytes: bytes, max_pages: int = 50) -> tuple[list[ExtractedTable], list[str], dict]:
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Not a valid PDF file")
    warnings, tables, stats = [], [], {"pages": 0, "ocr_pages": 0, "native_pages": 0}
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if doc.page_count > max_pages:
            raise ValueError(f"This PDF has {doc.page_count} pages; maximum allowed is {max_pages}")
        stats["pages"] = doc.page_count
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_no = i + 1
                local = []
                for strategy in ({"vertical_strategy": "lines", "horizontal_strategy": "lines"},
                                 {"vertical_strategy": "text", "horizontal_strategy": "text", "min_words_vertical": 3}):
                    try:
                        found = page.extract_tables(table_settings=strategy)
                    except Exception as exc:
                        warnings.append(f"Page {page_no}: table extraction attempt failed ({exc})")
                        found = []
                    local = [t for raw in found if (t := parse_grid(raw, page_no, "native"))]
                    if local:
                        break
                # If table extractor found only tiny fragments, let OCR handle scans.
                if local:
                    stats["native_pages"] += 1
                    tables.extend(local)
                elif len(page.extract_text() or "") < 35:
                    found, messages = scan_page(doc[i], page_no)
                    stats["ocr_pages"] += 1
                    warnings.extend(messages)
                    tables.extend(found)
                else:
                    warnings.append(f"Page {page_no}: selectable text present, but no table detected")
    return merge_tables(tables), warnings, stats


def merge_tables(tables: list[ExtractedTable]) -> list[ExtractedTable]:
    merged: list[ExtractedTable] = []
    for t in tables:
        t.rows = [r for r in t.rows if not is_repeat_header(r, t.headers)]
        previous = merged[-1] if merged else None
        if previous and t.pages[0] == previous.pages[-1] + 1 and header_similarity(previous.headers, t.headers) >= 0.84:
            # Remove only a boundary overlap, never global identical transactions.
            overlap = 0
            for n in range(1, min(5, len(previous.rows), len(t.rows)) + 1):
                if previous.rows[-n:] == t.rows[:n]:
                    overlap = n
            previous.rows.extend(t.rows[overlap:])
            previous.pages.extend(t.pages)
            previous.method = "hybrid" if previous.method != t.method else previous.method
        else:
            merged.append(t)
    for i, t in enumerate(merged, 1):
        t.name = f"Table_{i:02d}"
    return merged


def validate(tables: list[ExtractedTable]) -> list[dict]:
    issues = []
    for t in tables:
        width = len(t.headers)
        if not t.rows:
            issues.append({"table": t.name, "row": 0, "severity": "warning", "issue": "No data rows"})
        for i, row in enumerate(t.rows, 2):
            if len(row) != width:
                issues.append({"table": t.name, "row": i, "severity": "error", "issue": "Column misalignment"})
            if not any(clean(v) for v in row):
                issues.append({"table": t.name, "row": i, "severity": "warning", "issue": "Entirely empty row"})
            elif sum(not clean(v) for v in row) > width // 2:
                issues.append({"table": t.name, "row": i, "severity": "review", "issue": "Most cells blank"})
        # Validate explicit total rows for numeric columns, ignoring unrelated text.
        for i, row in enumerate(t.rows):
            if not likely_total(row):
                continue
            previous = t.rows[:i]
            for j, value in enumerate(row):
                target = numeric(value)
                if target is None or j < 1:
                    continue
                values = [numeric(r[j]) for r in previous if len(r) > j and not likely_total(r)]
                known = [x for x in values if x is not None]
                if len(known) >= 2 and abs(sum(known) - target) > max(0.02, abs(target) * 0.001):
                    issues.append({"table": t.name, "row": i+2, "severity": "review", "issue": f"Potential total mismatch in '{t.headers[j]}': displayed {target:g}, detail sum {sum(known):g}"})
    return issues


def export_excel(tables: list[ExtractedTable], issues: list[dict], stats: dict) -> bytes:
    """Create an Excel workbook using the publicly installable openpyxl package."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)
    header_fill = PatternFill("solid", fgColor="164E63")
    header_font = Font(bold=True, color="FFFFFF")

    def populate(sheet, rows, widths=None):
        for values in rows:
            sheet.append(["" if v is None else str(v) for v in values])
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        sheet.row_dimensions[1].height = 26
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for col_idx in range(1, max(sheet.max_column, 1) + 1):
            width = widths.get(col_idx, 19) if widths else 19
            sheet.column_dimensions[get_column_letter(col_idx)].width = width

    if not tables:
        ws = wb.create_sheet("No_tables")
        populate(ws, [["No tables extracted; inspect diagnostics."]], {1: 55})
    for t in tables:
        ws = wb.create_sheet(t.name[:31])
        populate(ws, [t.headers] + t.rows)

    ws = wb.create_sheet("Validation")
    populate(ws, [["Table", "Excel row", "Severity", "Description"]] + [
        [x["table"], x["row"], x["severity"], x["issue"]] for x in issues
    ], {1: 23, 2: 14, 3: 16, 4: 76})

    ws = wb.create_sheet("Provenance")
    populate(ws, [["Table", "Source pages", "Extraction method", "Data rows"]] + [
        [t.name, ", ".join(map(str, t.pages)), t.method, len(t.rows)] for t in tables
    ], {1: 25, 2: 25, 3: 25, 4: 16})
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def process(pdf_bytes: bytes) -> tuple[bytes, list[ExtractedTable], list[dict], list[str], dict]:
    tables, warnings, stats = extract_tables(pdf_bytes)
    issues = validate(tables)
    excel = export_excel(tables, issues, stats)
    return excel, tables, issues, warnings, stats

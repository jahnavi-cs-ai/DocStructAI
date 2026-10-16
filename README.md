# DocuStruct AI — PDF / scanned document to Excel

**Incuxai AI Agent Development Challenge 2026 — prototype.** A hybrid, auditable PDF-table extraction application built with Python, Streamlit and open-source tools.

## Features
- Upload PDFs, reject documents longer than **50 pages**.
- Extract tables from digital PDFs using pdfplumber's line-detection and text-detection modes; tables with **10+ columns** are supported when the layout is detectable.
- Use **Tesseract OCR** on image-only/scanned pages (requires external Tesseract installation).
- Detect header rows; merge sequential-page tables with similar headers; remove repeated headers and exact boundary overlap rows.
- Export an Excel workbook containing tables, **Validation** and **Provenance** worksheets.
- Flag suspicious missing cells and potential amount-total inconsistencies for review. Show diagnostics without modifying original extracted values.

## Install (Windows PowerShell)
```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
Install **Tesseract OCR** separately, and make sure `tesseract --version` works in a fresh terminal. On Windows you can install Tesseract from a reputable maintained distribution; add its installation folder to PATH. This is required **only for scanned PDFs**.

## Run
```powershell
streamlit run app.py
```
Upload your PDF and click **Extract tables**, review warnings, then download Excel.

## Sample documents / evaluation
Three **synthetic** documents are available in `samples/`:
1. `01_digital_11_columns.pdf` — digital table with 11 columns.
2. `02_multipage_statement.pdf` — three pages with repeated headers and continuation rows.
3. `03_scanned_image_table.pdf` — raster/image-only scanned PDF.

Every document has a matching `_truth.csv` source-of-truth file. The included `evaluate.py` computes exact row/column cell matches and row recall, and attempts to export each converted Excel file in `samples/`.

```powershell
python make_samples.py   # regenerate dummy test files (optional)
python evaluate.py       # extraction benchmark and output files
pytest -q
```

## Architecture
`app.py` → `docustruct/pipeline.py:process` → pdfplumber native tables / Tesseract OCR → table continuation merge → validation checks → `openpyxl` Excel export.

## Current limitations (important for judges)
- OCR is **heuristic**, not guaranteed for every scan: skewed, handwritten, low-resolution, merged-cell or borderless documents may need manual correction.
- Text-based extraction can mistake paragraphs for tables. Column clustering on OCR pages can fragment long text.
- Only **exact repeated boundary rows** are removed, to preserve legitimate duplicate transactions.
- Total-validation flags are heuristic; totals that include tax, fees or subsets may be flagged incorrectly.
- The application does not claim a measured accuracy percentage until `evaluate.py` is run in the final judging environment; check results yourself before including a number in a submission.

## How to record a 2–5 minute demo
Show: app startup → upload 11-column document → preview and Excel workbook → upload multi-page document → show merged rows/provenance → upload raster-only document → demonstrate OCR and validation warnings → show source code and test report.

## Attribution
PDF extraction: pdfplumber + PyMuPDF. OCR: pytesseract + Tesseract. Data preview: pandas. Excel: openpyxl. UI: Streamlit. Sample PDF generation: ReportLab + Pillow. All source code here is a reference implementation; review, test, and adapt it before submission in accordance with the challenge's original-work rules.

## Premium dashboard (2026 challenge edition)

The Streamlit interface now includes a dark responsive dashboard, local processing status,
PDF upload and first-page preview, per-document extraction metrics, extraction results tabs,
validation issues, processing diagnostics, and Excel download. The application is **DocuStruct AI**;
**INCUXAI** is credited as the challenge organizer, not misrepresented as the app publisher.

Run from this directory using `python -m streamlit run app.py`.
The dashboard does not require an API key; scanned PDFs need the Tesseract OCR desktop
executable available on PATH. The processing engine limits PDFs to 50 pages.

The page and extracted-row counts are descriptive metrics, **not accuracy rates**.
Local tests are examples only; manually verify financial amounts and difficult scans.

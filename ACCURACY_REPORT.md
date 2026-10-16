# Benchmark and Validation Report

Run date: 15 October 2026. Environment: local Python with Tesseract OCR installed. These are synthetic, controlled documents and **not** indicative of general PDF accuracy.

| Test document | Pages | Columns | True rows | Extracted rows | Exact-row recall | Exact-cell recall |
|---|---:|---:|---:|---:|---:|---:|
| Digital 11-column invoice | 1 | 11 | 8 | 8 | 100% | 100% |
| Multi-page statement | 3 | 10 | 32 | 32 | 100% | 100% |
| Image-only scanned table | 1 | 4 | 8 | 8 | 87.5% | 96.9% |

**Method:** Compare extraction output with separately generated `*_truth.csv` files, cell-by-cell in row order. Exact-row recall = correctly reproduced complete rows / total truth rows. Exact-cell recall = correctly reproduced individual cells / total truth cells. The OCR case misread one numeral (`1` as `i`) and should be manually reviewed.

**Validation:** Basic missing cell/column width checks; total rows compared with detail sums where applicable. These synthetic files do not test total reconciliation, fragmented cells, handwriting or all page formats. The `Validation` Excel worksheet records flagged issues and `Provenance` maps extracted tables to pages.

**Reproduce:** `python evaluate.py` writes `samples/accuracy_report.json` and converted Excel results. `pytest -q` runs unit tests for boundary overlap merging and total mismatch detection.

**Limitations:** OCR quality depends on Tesseract availability, scan resolution, rotation and column boundaries. No single tested PDF establishes performance on hidden judge documents. Cases requiring human review are not auto-corrected.

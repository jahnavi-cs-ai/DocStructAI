"""Local reproducible benchmark: tests 3 synthetic PDFs against exact CSV cell values."""
import csv
import json
from pathlib import Path
from docustruct.pipeline import process

base = Path(__file__).parent / "samples"
metrics = []
for pdf in sorted(base.glob("*.pdf")):
    truth = list(csv.reader((base/(pdf.stem+"_truth.csv")).open(newline="")))
    try:
        excel, tables, issues, warnings, stats = process(pdf.read_bytes())
        (base/(pdf.stem+"_converted.xlsx")).write_bytes(excel)
        expected = truth[1:]
        matching = max(tables, key=lambda t: len(t.rows), default=None)
        actual = matching.rows if matching else []
        headers_correct = bool(matching and matching.headers == truth[0])
        row_exact = sum(1 for i, row in enumerate(expected) if i<len(actual) and row == actual[i])
        cell_count = sum(len(r) for r in expected)
        exact_cells = sum(sum(a==b for a,b in zip(exp, actual[i])) for i,exp in enumerate(expected) if i<len(actual))
        record = {"document":pdf.name,"pages":stats["pages"],"ground_truth_rows":len(expected),"extracted_rows":len(actual),"ground_truth_columns":len(truth[0]),"extracted_columns":len(matching.headers) if matching else 0,"headers_exact":headers_correct,"row_exact_recall":round(row_exact/max(1,len(expected)),3),"cell_exact_recall":round(exact_cells/max(1,cell_count),3),"review_flags":len(issues),"warnings":warnings}
    except Exception as exc:
        record={"document":pdf.name,"error":str(exc)}
    print(record)
    metrics.append(record)
(base/"accuracy_report.json").write_text(json.dumps(metrics,indent=2))
print("Written samples/accuracy_report.json and converted workbooks for successful PDFs")

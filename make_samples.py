"""Create dummy, non-personal PDF test cases and independent ground truth."""
import csv
import io
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, PageBreak, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4, landscape
from PIL import Image, ImageDraw, ImageFont

base = Path(__file__).resolve().parent / "samples"
base.mkdir(exist_ok=True)
styles = getSampleStyleSheet()


def create(name, headers, rows, pagesize=landscape(A4), chunks=None):
    path = base / (name + ".pdf")
    story = []
    chunks = chunks or [rows]
    for k, batch in enumerate(chunks):
        if k:
            story.append(PageBreak())
        story.append(Paragraph("Dummy data — " + name.replace("_", " "), styles["Heading2"]))
        story.append(Spacer(1, 14))
        table = Table([headers]+batch, repeatRows=1, colWidths=(pagesize[0]-66)/len(headers), rowHeights=23)
        table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.6,colors.HexColor("#97a7b9")), ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dbeafe")), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8), ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
        story.append(table)
    SimpleDocTemplate(str(path), pagesize=pagesize, topMargin=34, bottomMargin=34, leftMargin=32, rightMargin=32).build(story)
    with (base / (name + "_truth.csv")).open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    return path


h1=["Invoice", "SKU", "Item", "Qty", "Unit Price", "Tax", "Amount", "Currency", "Date", "Status", "Region"]
r1=[[f"INV-{100+i}", f"SKU-{i:03}", f"Widget{i}", str(i%5+1), "125.00", "12.50", f"{(i%5+1)*125:.2f}", "INR", "2026-10-10", "Paid", "South"] for i in range(1,9)]
create("01_digital_11_columns",h1,r1)

h2=["Txn ID", "Date", "Description", "Debit", "Credit", "Balance", "Type", "Branch", "Ref", "Status"]
r2=[[f"TXN{i:04}", "2026-10-11", f"Payment{i}", str(i*10), "0", str(9000-i*10), "POS", "HYD", f"REF{i:03}", "Posted"] for i in range(1,33)]
create("02_multipage_statement",h2,r2,chunks=[r2[:11],r2[11:22],r2[22:]])

h3=["Item", "Quantity", "Price", "Amount"]
r3=[[f"Part-{i}",str(i),"20",str(i*20)] for i in range(1,9)]
# Raster-only scanned PDF (text exists exclusively inside bitmap)
img=Image.new("RGB",(1800,1300),"white")
d=ImageDraw.Draw(img)
try:
    font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",30)
except OSError:
    font=ImageFont.load_default()
xs=[75,505,940,1350,1730]
ys=[110+i*100 for i in range(len(r3)+2)]
for x in xs: d.line((x,ys[0],x,ys[-1]),fill="black",width=3)
for y in ys: d.line((xs[0],y,xs[-1],y),fill="black",width=3)
for i,row in enumerate([h3]+r3):
    for j,text in enumerate(row): d.text((xs[j]+13,ys[i]+28),text,fill="black",font=font)
img.convert("RGB").save(base/"03_scanned_image_table.pdf","PDF",resolution=160)
with (base/"03_scanned_image_table_truth.csv").open("w",newline="") as f:
    w=csv.writer(f); w.writerow(h3); w.writerows(r3)
print("Generated 3 sample PDFs and truth CSVs")

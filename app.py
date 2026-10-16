"""DocuStruct AI — premium Streamlit dashboard for PDF-to-Excel extraction."""
from __future__ import annotations
import hashlib
import io
import os
from datetime import datetime

import fitz
import pandas as pd
import streamlit as st
from docustruct.pipeline import process

st.set_page_config(page_title="DocuStruct AI | Document Intelligence", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
html, body, [class*="css"], [data-testid="stAppViewContainer"] {font-family:'DM Sans',sans-serif;}
[data-testid="stAppViewContainer"] {background: radial-gradient(ellipse at 75% 0%,#14284a 0%,#0b1221 44%,#080e1b 100%); color:#e9f1ff;}
[data-testid="stSidebar"] {background:#0c1629; border-right:1px solid #263756;}
[data-testid="stHeader"] {background:rgba(11,18,33,.65);}
[data-testid="stToolbar"] {right:1rem;}
h1,h2,h3,h4 {font-family:'Space Grotesk',sans-serif !important;letter-spacing:-.025em;}
h1 {font-size:2.6rem !important;}
[data-testid="stMetric"] {background:#111e33; border:1px solid #263b5e; border-radius:15px; padding:1.2rem; min-height:118px;}
[data-testid="stMetricValue"] {font-family:'Space Grotesk';font-weight:700;color:#eef7ff;}
[data-testid="stFileUploader"] {border:1px dashed #4685d3; background:#101e35; border-radius:18px;padding:8px;}
[data-testid="stFileUploaderDropzone"] {background:transparent;}
[data-testid="stDataFrame"] {border-radius:12px;overflow:hidden;}
.stButton>button[kind="primary"], [data-testid="stDownloadButton"] button {background:linear-gradient(95deg,#2675ef,#34a8f5);color:white;border:0;border-radius:10px;font-weight:700;}
.stButton>button {border-radius:10px;}
[data-testid="stExpander"] {background:#102036; border:1px solid #254264; border-radius:12px;}
[data-testid="stAlert"] {border-radius:12px;}
.hero {padding:29px 32px;border:1px solid #32517b; border-radius:22px;background:linear-gradient(120deg,#172c4b,#111d36 60%,#152e49);box-shadow:0 20px 70px #050b1933; margin-bottom:18px;}
.eyebrow {color:#76bbff;letter-spacing:.16em;font-size:.73rem;font-weight:700;text-transform:uppercase;}
.hero h1 {margin:.35rem 0 .25rem 0;color:#fff;font-size:2.75rem;}
.hero p {color:#b6c8e1;max-width:740px;margin:0;font-size:.98rem;line-height:1.7;}
.tag {display:inline-block;margin:0 7px 12px 0;border:1px solid #3e74ba;color:#8dc4ff;background:#17345c;border-radius:99px;padding:5px 11px;font-size:.72rem;letter-spacing:.025em;font-weight:600;}
.section {margin-top:18px;color:#eaf5ff;font-family:'Space Grotesk';font-size:1.32rem;font-weight:700;}
.mini {color:#91a7c4;font-size:.91rem;margin-bottom:13px;}
.feature {min-height:155px;padding:20px;border-radius:16px;border:1px solid #2d4669;background:linear-gradient(155deg,#162843,#101b30);margin-top:5px;}
.feature .f-icon {font-size:1.55rem;margin-bottom:10px;}
.feature .f-title {font-weight:700;color:#f4f8ff;margin-bottom:7px;}
.feature .f-body {font-size:.83rem;color:#aebdd4;line-height:1.6;}
.side-brand {font-family:'Space Grotesk';font-weight:700;font-size:1.65rem;color:#f7fbff;margin-bottom:1rem;}
.side-status {background:#12372e;border:1px solid #216a54;border-radius:12px;padding:14px;color:#75e3b2;font-weight:700;}
.side-note {background:#142741;border:1px solid #28517f;border-radius:12px;padding:14px;color:#b6d6ff;font-size:.86rem;line-height:1.65;}
.footer {font-size:.78rem;color:#829bbd;text-align:center;padding:20px 4px 4px;}
</style>
"""
st.markdown(STYLES, unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="side-brand">◈ DocuStruct <span style="color:#59aaff">AI</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="side-status">● &nbsp; Local extraction engine ready</div>', unsafe_allow_html=True)
    st.write('')
    st.markdown('### ⚙️ Extraction settings')
    show_preview = st.toggle('Show PDF page preview', value=True)
    show_diagnostics = st.toggle('Display extraction diagnostics', value=True)
    st.caption('Supported: PDF • up to 50 pages • digital tables + local OCR fallback')
    st.write('')
    st.markdown('<div class="side-note">🔒 <b>Local-first processing</b><br>Documents are processed in the running Python environment. No Gemini API key required. Scanned pages require separately installed Tesseract OCR.</div>', unsafe_allow_html=True)
    st.write('')
    st.caption('Challenge organizer: INCUXAI · 2026')
    st.caption('Made for the AI Agent Development Challenge')

st.markdown('''<div class="hero">
<span class="tag">◆ DOCUMENT INTELLIGENCE</span><span class="tag">50-PAGE PIPELINE</span><span class="tag">QUALITY CHECKS</span>
<div class="eyebrow">PDF-TO-EXCEL AUTOMATION WORKSPACE</div>
<h1>Transform documents.<br><span style="color:#77b8ff">Unlock structured data.</span></h1>
<p>Convert digital and scanned PDF tables into organized Excel workbooks. Keep page provenance, combine matching multi-page tables, and review suspicious values before using your data.</p>
</div>''', unsafe_allow_html=True)

st.markdown('<div class="section">01 / Upload your document</div>', unsafe_allow_html=True)
st.markdown('<div class="mini">Add a PDF to begin. Processing starts only when you select Run extraction.</div>', unsafe_allow_html=True)
upload = st.file_uploader('Choose a PDF', type=['pdf'], label_visibility='collapsed', help='PDF files up to 50 pages')

if 'result' not in st.session_state:
    st.session_state.result = None
if upload is not None:
    raw = upload.getvalue()
    signature = hashlib.sha256(raw).hexdigest()
    try:
        document = fitz.open(stream=raw, filetype='pdf')
        page_count = len(document)
        total_size = len(raw) / (1024 * 1024)
        is_encrypted = document.needs_pass
        document.close()
        ca, cb, cc = st.columns(3)
        ca.metric('Document', upload.name[:24] + ('…' if len(upload.name) > 24 else ''))
        cb.metric('Pages detected', page_count)
        cc.metric('File size', f'{total_size:.2f} MB')
        if is_encrypted:
            st.error('Encrypted PDFs are not supported. Upload an unlocked copy.')
        elif page_count > 50:
            st.error(f'This PDF has {page_count} pages; the challenge limit is 50.')
        else:
            if show_preview:
                with st.expander('👁️ Preview first page', expanded=False):
                    try:
                        preview_doc = fitz.open(stream=raw, filetype='pdf')
                        preview_pix = preview_doc[0].get_pixmap(matrix=fitz.Matrix(1.25,1.25), alpha=False)
                        st.image(preview_pix.tobytes('png'), width=600)
                        preview_doc.close()
                    except Exception as exc:
                        st.info(f'Preview unavailable: {exc}')
            if st.button('⚡ Run intelligent extraction', type='primary', use_container_width=True):
                with st.status('Analyzing pages, reconstructing tables and checking quality…', expanded=True) as status:
                    try:
                        st.write('Reading PDF structure and identifying tables…')
                        workbook, tables, issues, warnings, stats = process(raw)
                        st.write('Merging matching tables and producing Excel workbook…')
                        st.session_state.result = (signature, workbook, tables, issues, warnings, stats)
                        status.update(label='Extraction complete — review results below', state='complete', expanded=False)
                    except Exception as exc:
                        st.session_state.result = None
                        status.update(label='Extraction could not complete', state='error', expanded=True)
                        st.error(f'Extraction failed: {exc}')
                        st.info('For scanned PDFs, install the Tesseract executable in addition to Python pytesseract. See README.')
    except Exception as exc:
        st.error(f'Unable to open this PDF: {exc}')

result = st.session_state.result
if upload is not None and result is not None and result[0] == hashlib.sha256(upload.getvalue()).hexdigest():
    _, workbook, tables, issues, warnings, stats = result
    st.markdown('<div class="section">02 / Extraction insights</div>', unsafe_allow_html=True)
    st.markdown('<div class="mini">Metrics describe detected structure, not independently measured OCR accuracy.</div>', unsafe_allow_html=True)
    r1, r2, r3, r4 = st.columns(4)
    r1.metric('Pages scanned', stats.get('pages', 0))
    r2.metric('Tables found', len(tables))
    r3.metric('Rows extracted', sum(len(t.rows) for t in tables))
    r4.metric('Review flags', len(issues))
    r5, r6, r7 = st.columns(3)
    r5.metric('Native pages', stats.get('native_pages', 0))
    r6.metric('OCR pages', stats.get('ocr_pages', 0))
    r7.metric('Extraction notices', len(warnings))
    st.download_button('⬇️ Download Excel workbook', data=workbook,
        file_name=upload.name.rsplit('.',1)[0]+'_DocuStruct.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        type='primary', use_container_width=True)
    st.markdown('<div class="section">03 / Data review</div>', unsafe_allow_html=True)
    data_tab, validation_tab, log_tab = st.tabs(['📊 Extracted tables', '🛡️ Quality validation', '📋 Processing report'])
    with data_tab:
        if not tables:
            st.warning('No structured tables detected. Check the PDF layout or scan quality.')
        for table in tables:
            desc = f'{table.name or "Detected table"} · {len(table.headers)} columns · {len(table.rows)} rows · pages {", ".join(map(str,table.pages))}'
            with st.expander(desc, expanded=True):
                st.caption(f'Method: {table.method}. Preview shows extracted values without inventing missing cells.')
                st.dataframe(pd.DataFrame(table.rows, columns=table.headers), use_container_width=True, hide_index=True)
    with validation_tab:
        if issues:
            st.warning(f'{len(issues)} issue(s) identified for manual review.')
            st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)
        else:
            st.success('No rule-based issues found. This does not guarantee accuracy.')
    with log_tab:
        st.write({'pages': stats.get('pages',0), 'native_pages':stats.get('native_pages',0), 'ocr_pages':stats.get('ocr_pages',0), 'tables':len(tables)})
        if warnings and show_diagnostics:
            for warning in warnings:
                st.warning(warning)
        elif warnings:
            st.info(f'{len(warnings)} notices recorded. Enable diagnostics in sidebar to view.')
        else:
            st.success('No processing notices.')
else:
    st.markdown('<div class="section">Why DocuStruct AI?</div>', unsafe_allow_html=True)
    f1, f2, f3 = st.columns(3)
    with f1:
        st.markdown('<div class="feature"><div class="f-icon">◈</div><div class="f-title">Hybrid extraction engine</div><div class="f-body">Native table parsing for digital files, with image OCR for pages that cannot be extracted as text.</div></div>', unsafe_allow_html=True)
    with f2:
        st.markdown('<div class="feature"><div class="f-icon">⛓</div><div class="f-title">Multi-page continuity</div><div class="f-body">Merges consecutive tables with matching header structures and removes repeated headers.</div></div>', unsafe_allow_html=True)
    with f3:
        st.markdown('<div class="feature"><div class="f-icon">✓</div><div class="f-title">Transparent validation</div><div class="f-body">Surfaces suspicious cells and totals in a dedicated review sheet, preserving original extracted data.</div></div>', unsafe_allow_html=True)

st.markdown('<div class="footer">DOCUSTRUCT AI · Built for the INCUXAI AI Agent Development Challenge 2026 · Local-first document intelligence</div>', unsafe_allow_html=True)

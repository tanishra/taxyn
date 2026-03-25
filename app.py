"""
streamlit_app.py — Taxyn Test UI
Run: streamlit run streamlit_app.py
"""

import streamlit as st
import requests
import time

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Taxyn", page_icon="📄", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: #0f0c29; }
    section[data-testid="stSidebar"] { background: #1a1730 !important; border-right: 1px solid #302b63; min-width: 220px !important; max-width: 220px !important; }
    .taxyn-header { background: linear-gradient(135deg, #302b63 0%, #24243e 100%); border: 1px solid #FF6B6B30; border-radius: 12px; padding: 20px 28px; margin-bottom: 20px; }
    .taxyn-title { font-size: 32px; font-weight: 700; color: #FF6B6B; margin: 0; }
    .taxyn-sub { color: #9999bb; font-size: 13px; margin: 4px 0 0; }
    .result-card { background: #1a1730; border: 1px solid #302b63; border-radius: 10px; padding: 16px; margin-bottom: 10px; }
    .flag-item { background: #FF6B6B15; border-left: 3px solid #FF6B6B; border-radius: 4px; padding: 7px 12px; margin: 4px 0; font-size: 12px; color: #ffaaaa; font-family: 'JetBrains Mono', monospace; }
    .field-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #302b6340; font-size: 13px; }
    .field-key { color: #9999bb; font-family: 'JetBrains Mono', monospace; font-size: 11px; }
    .field-val { color: #e2e2f0; font-weight: 600; }
    .metric-box { background: #24243e; border: 1px solid #302b63; border-radius: 8px; padding: 12px 14px; text-align: center; }
    .metric-val { font-size: 22px; font-weight: 700; color: #FF6B6B; }
    .metric-label { font-size: 10px; color: #9999bb; letter-spacing: 0.1em; text-transform: uppercase; margin-top: 2px; }
    .stButton > button { background: linear-gradient(135deg, #FF6B6B, #ee5a24) !important; color: white !important; border: none !important; border-radius: 8px !important; font-weight: 600 !important; width: 100% !important; padding: 10px !important; }
    .step-box { background: #1a1730; border: 1px solid #302b63; border-radius: 8px; padding: 12px; text-align: left; height: 100%; }
</style>
""", unsafe_allow_html=True)

# ── Compact Sidebar ──────────────────────────────────────────
with st.sidebar:
    # API status — inline HTML, no padding bloat
    try:
        r = requests.get(f"{API_BASE}/health", timeout=2)
        api_html = '<span style="color:#00FFB2;font-size:12px;">🟢 API Online</span>'
    except Exception:
        api_html = '<span style="color:#FF6B6B;font-size:12px;">🔴 Offline — run python main.py</span>'

    tenant_id = st.text_input("Firm ID", value="firm_001")
    doc_type = st.selectbox("Doc Type",
        ["invoice", "gst_return", "bank_statement", "tds_certificate", "unknown"])

    st.markdown(api_html, unsafe_allow_html=True)

    # Pending queue — compact inline
    if st.button("↻ Refresh Queue"):
        try:
            r = requests.get(f"{API_BASE}/api/v1/review/pending", timeout=3)
            st.session_state["pending"] = r.json().get("pending_count", 0)
        except Exception:
            st.session_state["pending"] = "—"
    pending = st.session_state.get("pending", "—")
    st.markdown(f'<span style="color:#9999bb;font-size:12px;">📋 Pending reviews: <b style="color:#FF6B6B">{pending}</b></span>', unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#302b63;margin:10px 0"/><span style="color:#555577;font-size:11px;">Taxyn v1.0</span>', unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────
st.markdown("""
<div class="taxyn-header">
    <p class="taxyn-title">📄 Taxyn</p>
    <p class="taxyn-sub">AI Compliance Document Automation · Upload a PDF to extract structured data instantly</p>
</div>
""", unsafe_allow_html=True)

# ── Upload + Result ──────────────────────────────────────────
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.markdown("**📤 Upload Document**")
    uploaded_file = st.file_uploader("Drop a PDF", type=["pdf"], label_visibility="collapsed")
    if uploaded_file:
        st.markdown(f"""
        <div class="result-card">
            <div class="field-key">FILE</div>
            <div class="field-val">📄 {uploaded_file.name}</div>
            <div class="field-key" style="margin-top:6px">SIZE</div>
            <div class="field-val">{uploaded_file.size/1024:.1f} KB</div>
        </div>""", unsafe_allow_html=True)
    extract_btn = st.button("⚡ Extract Document", disabled=not uploaded_file)

with col2:
    st.markdown("**📊 Extraction Result**")

    if extract_btn and uploaded_file:
        st.info("⏳ Extraction may take longer for complex PDFs when Google Document AI fallback is used.")
        with st.spinner("Extracting → Parsing → Validating..."):
            try:
                start = time.time()
                response = requests.post(
                    f"{API_BASE}/api/v1/extract",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                    data={"tenant_id": tenant_id, "doc_type": doc_type},
                    timeout=300,
                )
                elapsed = (time.time() - start) * 1000
                result = response.json()

                status = result.get("status", "unknown")
                confidence = result.get("confidence", 0)
                flags = result.get("compliance_flags", [])

                m1, m2, m3 = st.columns(3)
                with m1:
                    st.markdown(f"""<div class="metric-box">
                        <div class="metric-val">{'🟢' if confidence >= 0.85 else '🔴'} {confidence*100:.1f}%</div>
                        <div class="metric-label">Confidence</div></div>""", unsafe_allow_html=True)
                with m2:
                    st.markdown(f"""<div class="metric-box">
                        <div class="metric-val">{result.get('processing_time_ms', elapsed):.0f}ms</div>
                        <div class="metric-label">Time</div></div>""", unsafe_allow_html=True)
                with m3:
                    st.markdown(f"""<div class="metric-box">
                        <div class="metric-val">{'🔴' if flags else '🟢'} {len(flags)}</div>
                        <div class="metric-label">Flags</div></div>""", unsafe_allow_html=True)

                st.markdown("<br/>", unsafe_allow_html=True)

                extracted = result.get("extracted_data", {})
                display_fields = {k: v for k, v in extracted.items() if k not in {"raw_text","char_count"} and v}
                if display_fields:
                    st.markdown("**📋 Extracted Fields**")
                    rows = "".join(f"""<div class="field-row">
                        <span class="field-key">{k.replace('_',' ').upper()}</span>
                        <span class="field-val">{v}</span></div>""" for k, v in display_fields.items())
                    st.markdown(f'<div class="result-card">{rows}</div>', unsafe_allow_html=True)

                if flags:
                    st.markdown("**🚩 Compliance Flags**")
                    st.markdown("".join(f'<div class="flag-item">⚠ {f}</div>' for f in flags), unsafe_allow_html=True)
                else:
                    st.success("✅ No compliance issues found")

                if status == "needs_review":
                    st.warning(result.get("message", "Low confidence — sent to human review queue."))

                with st.expander("🔍 Raw JSON"):
                    st.json(result)

            except requests.exceptions.Timeout:
                st.error("❌ Timed out after 5 min.\nCheck terminal — server may still be processing.\nTry again — next run will be faster.")
            except requests.exceptions.ConnectionError:
                st.error("❌ API offline. Run: `python main.py`")
            except Exception as e:
                st.error(f"❌ {str(e)}")
    else:
        st.markdown("""<div class="result-card" style="text-align:center;padding:40px;color:#555577;">
            <div style="font-size:36px;margin-bottom:10px;">📭</div>
            <div style="font-size:13px;">Upload a PDF and click Extract</div>
        </div>""", unsafe_allow_html=True)

# ── Pipeline Steps ───────────────────────────────────────────
st.divider()
st.markdown("**🔄 Pipeline**")
steps = [
    ("01", "ExtractorTool", "pypdf first, Google Document AI fallback"),
    ("02", "ParserTool", "GPT-4o-mini extracts fields"),
    ("03", "ValidatorTool", "GST/PAN/GSTIN checks"),
    ("04", "ConfidenceScorer", "Scores each field 0→1"),
    ("05", "Confidence Gate", "≥0.85 → Done  <0.85 → HITL"),
]
cols = st.columns(5)
for i, (num, name, desc) in enumerate(steps):
    with cols[i]:
        st.markdown(f"""<div class="step-box">
            <div style="color:#FF6B6B;font-size:10px;font-family:monospace;margin-bottom:3px;">STEP {num}</div>
            <div style="color:#e2e2f0;font-weight:700;font-size:12px;margin-bottom:4px;">{name}</div>
            <div style="color:#9999bb;font-size:11px;line-height:1.5;">{desc}</div>
        </div>""", unsafe_allow_html=True)

"""
Noxora — Patient Report Generator
Streamlit app: reads patient data from Google Sheets → generates PDF report.
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from io import BytesIO
import sys, os

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Noxora | Report Generator",
    page_icon="🌙",
    layout="centered",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background: #F8F8F5; }
    h1 { color: #1E2538; }
    .stButton>button { background: #1E2538; color: white; border-radius: 6px; }
    .stButton>button:hover { background: #C9A96E; color: #1E2538; }
    .metric-box { background: white; border-radius: 8px; padding: 12px;
                  border: 1px solid #E0E0DA; text-align: center; }
    .metric-label { font-size: 10px; color: #888; text-transform: uppercase;
                    font-weight: bold; letter-spacing: 0.5px; }
    .metric-value { font-size: 22px; font-weight: bold; color: #1E2538; }
    .metric-delta { font-size: 12px; font-weight: bold; }
    .good { color: #2E7D32; } .bad { color: #B71C1C; } .neutral { color: #888; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
SHEET_URL = ("https://docs.google.com/spreadsheets/d/e/"
             "2PACX-1vSNC2iZ9JRcwaeFJVx9aPrJbLH_kfqMvI1-CvFvATJcx34-QI8Y1dtmu2ZaUPQ1FXoIubM1cihkNSP5"
             "/pub?output=csv")
PASSWORD = "Augustin1!"

# Column positions (0-indexed from raw CSV rows after header parsing)
C = {
    "name":        3,   "surname":     4,   "gender":      7,
    "age":         8,   "prog_date":   9,   "batch":       10,
    "location":    11,
    # Pre ISI
    "pre_isi_q1":  12,  "pre_isi_q2":  13,  "pre_isi_q3":  14,
    "pre_isi_q4":  15,  "pre_isi_q5":  16,  "pre_isi_q6":  17,
    "pre_isi_q7":  18,  "pre_isi_tot": 19,
    # Pre PSQI
    "pre_psqi_q1": 20,  "pre_psqi_q2": 21,  "pre_psqi_q3": 22,
    "pre_psqi_q4": 23,  "pre_psqi_q5a":24,  "pre_psqi_q5b":25,
    "pre_psqi_q5c":26,  "pre_psqi_q5g":30,  "pre_psqi_q5h":31,
    "pre_psqi_q6": 35,  "pre_psqi_q9": 38,
    "pre_psqi_eff":41,  "pre_psqi_tot":51,
    # Pre Sleep Habits
    "pre_hab_q1":  86,  "pre_hab_q3":  88,  "pre_hab_q4":  89,
    "pre_hab_q12": 97,  "pre_hab_score":107,"pre_hab_wknd":108,
    # 6W ISI
    "6w_isi_q1":  109, "6w_isi_q2":  110, "6w_isi_q3":  111,
    "6w_isi_q4":  112, "6w_isi_q5":  113, "6w_isi_q6":  114,
    "6w_isi_q7":  115, "6w_isi_tot": 116,
    # 6W PSQI
    "6w_psqi_q1": 117, "6w_psqi_q2": 118, "6w_psqi_q3": 119,
    "6w_psqi_q4": 120, "6w_psqi_q5a":121, "6w_psqi_q5b":122,
    "6w_psqi_q5c":123, "6w_psqi_q5g":127, "6w_psqi_q5h":128,
    "6w_psqi_q6": 132, "6w_psqi_q9": 135,
    "6w_psqi_eff":138, "6w_psqi_tot":148,
    # 6W Sleep Habits
    "6w_hab_q1":  149, "6w_hab_q3":  151, "6w_hab_q4":  152,
    "6w_hab_q12": 160, "6w_hab_score":170,"6w_hab_wknd":171,
    # 6W Satisfaction
    "sat_q1":     172, "sat_q2":     173, "sat_q3":     174,
    "sat_q4":     175, "sat_q5":     176,
    # Medical
    "med_other":   84,
}

# ── Auth ──────────────────────────────────────────────────────────────────────
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🌙 Noxora")
        st.markdown("### Report Generator")
        pwd = st.text_input("Password", type="password", placeholder="Enter password")
        if st.button("Login", use_container_width=True):
            if pwd == PASSWORD:
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("Incorrect password")
    st.stop()

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner="Loading patient data…")
def load_sheet():
    all_rows = pd.read_csv(SHEET_URL, header=None, dtype=str)
    # Build unique column names from row 2 (the main header)
    raw_names = all_rows.iloc[2].tolist()
    seen = {}
    col_names = []
    for n in raw_names:
        n = str(n).strip().replace("\n", " ") if pd.notna(n) else ""
        if n in seen:
            seen[n] += 1
            col_names.append(f"{n} #{seen[n]}")
        else:
            seen[n] = 0
            col_names.append(n)
    # Data rows start at index 6
    df = all_rows.iloc[6:].copy().reset_index(drop=True)
    df.columns = col_names
    # Keep only rows with a first name
    df = df[df.iloc[:, C["name"]].notna() &
            (df.iloc[:, C["name"]].str.strip() != "")]
    return df.reset_index(drop=True)


def val(row, key, default="—"):
    """Safe value extraction by column index."""
    try:
        idx = C[key]
        v = row.iloc[idx]
        if pd.isna(v) or str(v).strip() in ("", "NR", "NA", "#VALUE!"):
            return default
        return str(v).strip()
    except Exception:
        return default


def num(row, key, default=None):
    """Extract numeric value."""
    v = val(row, key, "")
    if v in ("", "—"):
        return default
    try:
        return float(str(v).replace("%", "").strip())
    except Exception:
        return default


# ── Main UI ───────────────────────────────────────────────────────────────────
st.markdown("## 🌙 Noxora — Report Generator")

try:
    df = load_sheet()
except Exception as e:
    st.error(f"Could not load Google Sheet: {e}")
    st.stop()

# Patient selection
names = (df.iloc[:, C["name"]].str.strip() + " " +
         df.iloc[:, C["surname"]].str.strip())
names = names[names.str.strip() != ""].reset_index(drop=True)

col_a, col_b, col_c = st.columns([2, 1, 1])
with col_a:
    selected = st.selectbox("Patient", names)
with col_b:
    report_type = st.selectbox("Report type", ["6 weeks", "3 months"])
with col_c:
    st.markdown("<br>", unsafe_allow_html=True)
    refresh = st.button("🔄 Refresh data")
    if refresh:
        st.cache_data.clear()
        st.rerun()

# Get patient row
idx = names[names == selected].index[0]
row = df.iloc[idx]

# ── Patient data summary ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Patient overview")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Patient", val(row, "name") + " " + val(row, "surname"))
c2.metric("Location", val(row, "location"))
c3.metric("Programme", val(row, "prog_date"))
c4.metric("Batch", val(row, "batch"))

# Key scores
st.markdown("#### Key scores")

pre_isi  = num(row, "pre_isi_tot")
post_isi = num(row, "6w_isi_tot") if report_type == "6 weeks" else num(row, "pre_isi_tot")
pre_psqi  = num(row, "pre_psqi_tot")
post_psqi = num(row, "6w_psqi_tot") if report_type == "6 weeks" else None
pre_hab   = num(row, "pre_hab_score")
post_hab  = num(row, "6w_hab_score") if report_type == "6 weeks" else None
pre_unp   = num(row, "pre_hab_q4")
post_unp  = num(row, "6w_hab_q4")

def delta_color(pre, post):
    if pre is None or post is None: return "neutral"
    return "good" if post < pre else ("bad" if post > pre else "neutral")

def show_metric(label, pre, post, low_is_good=True):
    if pre is None: pre = "—"
    if post is None: post = "—"
    try:
        delta = int(post) - int(pre)
        sign = "–" if delta < 0 else "+"
        clr = ("good" if delta < 0 else "bad") if low_is_good else ("good" if delta > 0 else "bad")
        delta_str = f'<span class="metric-delta {clr}">{sign}{abs(delta)} pts</span>'
    except Exception:
        delta_str = ""
    return f"""<div class="metric-box">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{pre} → {post}</div>
        {delta_str}
    </div>"""

c1, c2, c3 = st.columns(3)
with c1: st.markdown(show_metric("ISI Score", pre_isi, post_isi), unsafe_allow_html=True)
with c2: st.markdown(show_metric("PSQI Score", pre_psqi, post_psqi), unsafe_allow_html=True)
with c3: st.markdown(show_metric("Unprescribed Meds (0-3)", pre_unp, post_unp), unsafe_allow_html=True)

# Medication-adjusted ISI estimate
st.markdown("#### Medication-adjusted ISI")
pre_rx = num(row, "pre_hab_q3", 0)
post_rx = num(row, "6w_hab_q3", 0)
adj_note = ""
med_adj_post = post_isi
if pre_unp and post_unp and pre_isi and post_isi:
    reduction = (pre_unp - post_unp) if pre_unp > post_unp else 0
    med_adj_post = int(post_isi) - int(reduction)
    adj_note = f"Unprescribed meds reduced by {int(reduction)}/3 → adjusted ISI ≈ {med_adj_post}"

c1, c2 = st.columns(2)
med_adj_pre  = st.number_input("ISI pre (medication-adjusted)", value=int(pre_isi or 0), step=1)
med_adj_6w   = st.number_input("ISI 6W (medication-adjusted)", value=int(med_adj_post or 0), step=1)
if adj_note:
    st.caption(f"💡 Auto-estimate: {adj_note}. Adjust manually if needed.")

# Satisfaction (6W only)
sat_q1 = sat_q2 = sat_q3 = None
if report_type == "6 weeks":
    st.markdown("#### Patient satisfaction (6W)")
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Overall satisfaction (1-10)", val(row, "sat_q1"))
    with c2: st.metric("Time to feel effect (1-5)", val(row, "sat_q2"))
    with c3: st.metric("Likelihood to recommend (1-10)", val(row, "sat_q3"))
    try:
        sat_q1 = int(float(val(row, "sat_q1", "0")))
        sat_q2 = int(float(val(row, "sat_q2", "0")))
        sat_q3 = int(float(val(row, "sat_q3", "0")))
    except Exception:
        pass

# ── Clinical notes ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### ✏️ Your clinical notes")
st.caption("Fill in your observations below. These will appear in the report comment boxes.")

notes = {
    "medication":      st.text_area("Medication note", height=70,
                                    placeholder="Context on medication use, adjustments, physician discussions…"),
    "isi_comments":    st.text_area("ISI — clinical comments", height=70,
                                    placeholder="Describe insomnia profile, onset, contributing factors…"),
    "psqi_comments":   st.text_area("PSQI — clinical comments", height=70,
                                    placeholder="Components of concern: efficiency, latency, awakenings…"),
    "post_treatment":  st.text_area("Post-treatment observations", height=90,
                                    placeholder="Observable changes, symptom evolution, daytime functioning…"),
    "general":         st.text_area("General clinical observations", height=70,
                                    placeholder="Any additional observations from your interactions with the patient…"),
    "recommendations": st.text_area("Additional / personalised recommendations", height=90,
                                    placeholder="Specific actions for this patient beyond the standard recommendations…"),
}

# Programme details
st.markdown("---")
st.markdown("#### Programme details (not in sheet — fill manually)")
c1, c2 = st.columns(2)
with c1:
    num_stimulations = st.text_input("No. of stimulations", value="")
    lead_professional = st.text_input("Lead professional", value="Noxora Clinical Team")
with c2:
    report_date = st.text_input("Report date", value="")
    patient_id  = st.text_input("Patient ID", value=f"NX-{val(row, 'name', '').upper()[:3]}")

# ── Generate ──────────────────────────────────────────────────────────────────
st.markdown("---")

if st.button("▶ Generate Report", type="primary", use_container_width=True):
    with st.spinner("Generating PDF…"):
        # Build patient_data dict
        def v(key, default="[To be completed]"):
            return val(row, key, default)
        def n(key, default=0):
            return num(row, key, default) or default

        patient_data = {
            # Identity
            "first_name":   v("name").strip(),
            "last_name":    v("surname").strip(),
            "gender":       "Female" if v("gender", "").upper() == "F" else "Male",
            "age":          v("age"),
            "patient_id":   patient_id,
            "program_date": v("prog_date"),
            "batch":        v("batch"),
            "location":     v("location"),
            "report_type":  report_type,
            "num_stimulations": num_stimulations or "[To be completed]",
            "lead_professional": lead_professional,
            "report_date":  report_date or "[To be completed]",

            # Pre ISI
            "pre_isi_q": [n(f"pre_isi_q{i}") for i in range(1, 8)],
            "pre_isi_total": int(n("pre_isi_tot", 0)),

            # Pre PSQI
            "pre_psqi_bedtime":  v("pre_psqi_q1"),
            "pre_psqi_latency":  v("pre_psqi_q2"),
            "pre_psqi_wake":     v("pre_psqi_q3"),
            "pre_psqi_hours":    v("pre_psqi_q4"),
            "pre_psqi_q5a": n("pre_psqi_q5a"), "pre_psqi_q5b": n("pre_psqi_q5b"),
            "pre_psqi_q5c": n("pre_psqi_q5c"), "pre_psqi_q5g": n("pre_psqi_q5g"),
            "pre_psqi_q5h": n("pre_psqi_q5h"), "pre_psqi_q6":  n("pre_psqi_q6"),
            "pre_psqi_q9":  n("pre_psqi_q9"),
            "pre_psqi_efficiency": v("pre_psqi_eff", "—"),
            "pre_psqi_total": int(n("pre_psqi_tot", 0)),

            # Pre habits
            "pre_hab_bedtime":    v("pre_hab_q1"),
            "pre_hab_prescribed": n("pre_hab_q3"),
            "pre_hab_unprescribed": n("pre_hab_q4"),
            "pre_hab_stressed":   n("pre_hab_q12"),
            "pre_hab_score":      int(n("pre_hab_score", 0)),
            "pre_hab_weekend":    int(n("pre_hab_wknd", 0)),

            # 6W ISI
            "post_isi_q": [n(f"6w_isi_q{i}") for i in range(1, 8)],
            "post_isi_total": int(n("6w_isi_tot", 0)),
            "post_isi_med_adj": int(med_adj_6w),
            "pre_isi_med_adj":  int(med_adj_pre),

            # 6W PSQI
            "post_psqi_bedtime":  v("6w_psqi_q1"),
            "post_psqi_latency":  v("6w_psqi_q2"),
            "post_psqi_wake":     v("6w_psqi_q3"),
            "post_psqi_hours":    v("6w_psqi_q4"),
            "post_psqi_q5a": n("6w_psqi_q5a"), "post_psqi_q5b": n("6w_psqi_q5b"),
            "post_psqi_q5c": n("6w_psqi_q5c"), "post_psqi_q5g": n("6w_psqi_q5g"),
            "post_psqi_q5h": n("6w_psqi_q5h"), "post_psqi_q6":  n("6w_psqi_q6"),
            "post_psqi_q9":  n("6w_psqi_q9"),
            "post_psqi_efficiency": v("6w_psqi_eff", "—"),
            "post_psqi_total": int(n("6w_psqi_tot", 0)),

            # 6W habits
            "post_hab_bedtime":    v("6w_hab_q1"),
            "post_hab_prescribed": n("6w_hab_q3"),
            "post_hab_unprescribed": n("6w_hab_q4"),
            "post_hab_stressed":   n("6w_hab_q12"),
            "post_hab_score":      int(n("6w_hab_score", 0)),
            "post_hab_weekend":    int(n("6w_hab_wknd", 0)),

            # Satisfaction
            "sat_q1": sat_q1, "sat_q2": sat_q2, "sat_q3": sat_q3,
            "sat_feedback": val(row, "sat_q4", ""),
            "sat_other":    val(row, "sat_q5", ""),

            # Medical context
            "medical_other": v("med_other", ""),
        }

        # Import and call the report generator
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from generate_report import generate_pdf
            pdf_bytes = generate_pdf(patient_data, notes)
            st.session_state.pdf_bytes = pdf_bytes
            st.session_state.pdf_name  = (
                f"Noxora_Report_{patient_data['first_name']}_{patient_data['last_name']}"
                f"_{report_type.replace(' ', '')}.pdf"
            )
            st.success("✅ Report generated!")
        except Exception as e:
            st.error(f"Error generating report: {e}")
            import traceback
            st.code(traceback.format_exc())

if "pdf_bytes" in st.session_state:
    st.download_button(
        "⬇ Download PDF",
        data=st.session_state.pdf_bytes,
        file_name=st.session_state.pdf_name,
        mime="application/pdf",
        use_container_width=True,
        type="primary",
    )

# ── Logout ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("**Noxora** Report Generator")
    st.markdown("---")
    st.caption(f"Sheet refreshes every 5 min")
    if st.button("Logout"):
        st.session_state.auth = False
        st.rerun()

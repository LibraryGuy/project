import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. MOBILE & PWA CONFIGURATION ---
components.html(
    """
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <style>
        :root { color-scheme: light dark; }
    </style>
    """,
    height=0
)

st.set_page_config(page_title="2026 Intel Tracker", layout="wide", page_icon="🏛️")

# --- 2. API CONFIGURATION ---
try:
    CONGRESS_API_KEY = st.secrets["CONGRESS_API_KEY"].strip()
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"].strip()
except KeyError as e:
    st.error(f"Missing Secret Key: {e}. Check Streamlit Cloud Secrets.")
    st.stop()

# 2026 Intelligence Model
MODEL_ID = 'gemini-3-flash-preview' 
CONGRESS_SESSION = "119"
BASE_URL = "https://api.congress.gov/v3"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(MODEL_ID)

if 'bills_df' not in st.session_state:
    st.session_state.bills_df = pd.DataFrame()

# --- 3. DATA FETCHING (CACHED) ---

@st.cache_data(ttl=600)
def fetch_congress_data(endpoint):
    url = f"{BASE_URL}/{endpoint}?api_key={CONGRESS_API_KEY}&format=json&limit=20"
    try:
        resp = requests.get(url)
        return resp.json() if resp.status_code == 200 else None
    except: return None

@st.cache_data(ttl=3600)
def fetch_executive_orders():
    url = "https://www.federalregister.gov/api/v1/documents.json?conditions[type][]=PRESDOCU&conditions[presidential_document_type][]=executive_order&per_page=10"
    try:
        resp = requests.get(url)
        return resp.json().get('results', []) if resp.status_code == 200 else []
    except: return []

@st.cache_data(ttl=3600)
def fetch_scotus_cases():
    term = datetime.now().year if datetime.now().month >= 10 else datetime.now().year - 1
    url = f"https://api.oyez.org/cases?per_page=10&filter=term:{term}"
    try:
        resp = requests.get(url)
        return resp.json() if resp.status_code == 200 else []
    except: return []

# --- 4. INTELLIGENCE LOGIC (SMART CACHING) ---

def draw_risk_meter(score):
    """Visualizes legal risk on a 1-10 scale."""
    if score <= 3: color = "#28a745"   # Green
    elif score <= 7: color = "#ffc107" # Yellow
    else: color = "#dc3545"            # Red
    pct = score * 10
    st.markdown(f"""
        <div style="background-color: #e9ecef; border-radius: 10px; width: 100%; height: 15px; margin: 10px 0;">
            <div style="background-color: {color}; width: {pct}%; height: 15px; border-radius: 10px; transition: width 0.8s ease-in-out;"></div>
        </div>
        <p style="text-align: right; font-weight: bold; color: {color}; font-size: 0.9em;">Constitutionality Risk: {score}/10</p>
    """, unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def cached_ai_analyze(item_id, title, text, mode="impact"):
    """
    Prevents duplicate API calls. If the app reruns, 
    it retrieves analysis from local cache.
    """
    prompts = {
        "impact": f"Analyze economic impact for '{title}'. Winners/Losers (3 bullets each). Text: {text}",
        "sentiment": f"Analyze partisan lean for '{title}'. Is it bipartisan or polarized? Text: {text}",
        "constitution": f"""You are a Constitutional Scholar. Audit the following for legal risk.
            Title: {title} | Text: {text}
            IMPORTANT: Your response MUST start with 'Risk Score: [number]' (1-10). 
            Then identify statutory authority and potential litigation."""
    }
    try:
        response = model.generate_content(prompts[mode]).text
        score = 5
        if mode == "constitution" and "Risk Score:" in response:
            try:
                # Extracts the integer score for the risk meter
                score = int(response.split("Risk Score:")[1].split()[0].replace(',', '').strip())
            except: score = 5
        return score, response
    except Exception as e: return 0, f"AI Error: {e}"

# --- 5. UI DISPLAY ---

st.title("🏛️ 2026 Intel Policy Tracker")
st.caption(f"v3.0 Optimization Build • {datetime.now().strftime('%B %d, %Y')}")

# Mobile UI Overrides
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3.2em; font-weight: 600; }
    header {visibility: hidden;}
    [data-testid="stMetricValue"] { font-size: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📜 Legislation", "🖋️ Executive Actions", "⚖️ SCOTUS", "🔬 Deep Dive"])

with tab1:
    col1, col2 = st.columns([2,1])
    with col1:
        search = st.text_input("🔍 Search Bills", placeholder="Search keywords...")
    
    raw = fetch_congress_data(f"bill/{CONGRESS_SESSION}")
    if raw:
        df = pd.DataFrame(raw.get('bills', []))
        df['status'] = df['latestAction'].apply(lambda x: x.get('text', 'N/A'))
        if search:
            df = df[df['title'].str.contains(search, case=False) | df['number'].str.contains(search, case=False)]
        st.session_state.bills_df = df
        selection = st.dataframe(
            df[['number', 'title', 'status']], 
            use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="bill_table"
        )

with tab2:
    st.subheader("🖋️ Executive Orders Library")
    eo_list = fetch_executive_orders()
    for eo in eo_list:
        doc_id = eo.get('document_number')
        with st.expander(f"📄 {eo.get('title')}"):
            st.write(f"**Abstract:** {eo.get('abstract')}")
            st.link_button("🌐 Read Official Text", eo.get('html_url'))
            if st.button("⚖️ Run Judicial AI Review", key=f"rev_{doc_id}"):
                with st.spinner("Analyzing Presidential Authority..."):
                    # Using cached AI function to prevent redundant calls
                    score, review = cached_ai_analyze(doc_id, eo.get('title'), eo.get('abstract'), "constitution")
                    draw_risk_meter(score)
                    st.markdown(review)

with tab3:
    st.subheader("⚖️ SCOTUS Docket")
    sc_cases = fetch_scotus_cases()
    for case in sc_cases:
        with st.expander(f"⚖️ {case.get('name')} [{case.get('docket_number')}]"):
            st.write(case.get('description', 'Summary pending.'))
            st.link_button("Oyez Details", f"https://www.oyez.org/cases/{case.get('term')}/{case.get('docket_number')}")

with tab4:
    if selection and selection.get("selection") and selection["selection"]["rows"]:
        idx = selection["selection"]["rows"][0]
        bill = st.session_state.bills_df.iloc[idx]
        bill_id = bill['number']
        
        st.header(bill['title'])
        st.metric("Status", bill['number'], bill['status'])
        
        # Load Economic and Partisan results immediately (Cached)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("💰 Economic Impact")
            _, impact_res = cached_ai_analyze(bill_id, bill['title'], bill['title'], "impact")
            st.info(impact_res)
        with c2:
            st.subheader("⚖️ Partisan Sentiment")
            _, sentiment_res = cached_ai_analyze(bill_id, bill['title'], bill['title'], "sentiment")
            st.info(sentiment_res)
            
        st.divider()
        st.subheader("⚖️ Constitutional Audit")
        if st.button("⚖️ Run Legal Risk Analysis"):
            with st.spinner("Analyzing legal precedent..."):
                # Clicking this now won't trigger the c1/c2 sections to call Gemini again
                score, const_res = cached_ai_analyze(bill_id, bill['title'], bill['title'], "constitution")
                draw_risk_meter(score)
                st.warning(const_res)
    else:
        st.info("👈 Select a bill in the **Legislation** tab to begin analysis.")

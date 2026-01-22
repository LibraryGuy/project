import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
from datetime import datetime
import streamlit.components.v1 as components

# Forces mobile browsers to treat it like an app
components.html(
    """
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="apple-touch-icon" href="https://your-icon-url.png">
    """,
    height=0
)

# --- 1. CONFIGURATION ---
try:
    CONGRESS_API_KEY = st.secrets["CONGRESS_API_KEY"].strip()
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"].strip()
except KeyError as e:
    st.error(f"Missing Secret Key: {e}. Check Streamlit Cloud Secrets.")
    st.stop()

# 2026 Model Standard
MODEL_ID = 'gemini-3-flash-preview' 
CONGRESS_SESSION = "119"
BASE_URL = "https://api.congress.gov/v3"

# Initialize AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(MODEL_ID)

# Persistent State
if 'bills_df' not in st.session_state:
    st.session_state.bills_df = pd.DataFrame()

st.set_page_config(page_title="2026 Intel Tracker", layout="wide", page_icon="🏛️")

# --- 2. DATA FETCHING (THE TOOLS) ---

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
    # Oyez uses year-based terms
    term = datetime.now().year if datetime.now().month >= 10 else datetime.now().year - 1
    url = f"https://api.oyez.org/cases?per_page=10&filter=term:{term}"
    try:
        resp = requests.get(url)
        return resp.json() if resp.status_code == 200 else []
    except: return []

# --- 3. INTELLIGENCE LOGIC ---

def ai_analyze(text, title, mode="impact"):
    prompts = {
        "impact": f"Analyze economic impact for '{title}'. Winners/Losers (3 bullets each). Text: {text}",
        "sentiment": f"Analyze partisan lean for '{title}'. Is it bipartisan or polarized? Text: {text}",
        "constitution": f"You are a SCOTUS expert. Audit '{title}' for constitutional risks (Separation of Powers, Federalism). Rate risk 1-10. Text: {text}"
    }
    if not text or "not yet available" in text: return "Analysis pending official text."
    try:
        return model.generate_content(prompts[mode]).text
    except Exception as e: return f"AI Error: {e}"

# --- 4. UI DISPLAY ---

st.title("🏛️ 2026 Intel Policy Tracker")
st.caption(f"Real-time Intelligence Dashboard • {datetime.now().strftime('%B %d, %Y')}")

# Automated News Alerts (Top Ticker)
with st.expander("🔔 Recent Policy Alerts", expanded=False):
    orders = fetch_executive_orders()[:3]
    for eo in orders:
        st.write(f"**NEW EO:** {eo.get('title')} ({eo.get('publication_date')})")

tab1, tab2, tab3, tab4 = st.tabs(["📜 Legislation", "🖋️ Executive Actions", "⚖️ Supreme Court", "🔬 Intelligence Deep Dive"])

with tab1:
    col1, col2 = st.columns([2,1])
    with col1:
        search = st.text_input("🔍 Semantic Search (Keywords or Industry)", placeholder="e.g. 'semiconductors' or 'border'")
    with col2:
        status_filter = st.multiselect("Status", ["Introduced", "Passed House", "Became Law"])

    raw = fetch_congress_data(f"bill/{CONGRESS_SESSION}")
    if raw:
        df = pd.DataFrame(raw.get('bills', []))
        df['status'] = df['latestAction'].apply(lambda x: x.get('text', 'N/A'))
        
        # Filtering Logic
        if search:
            df = df[df['title'].str.contains(search, case=False) | df['number'].str.contains(search, case=False)]
        
        st.session_state.bills_df = df
        selection = st.dataframe(
            df[['number', 'title', 'status']], 
            use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="bill_table"
        )

with tab2:
    st.subheader("🖋️ Executive Orders library")
    eo_list = fetch_executive_orders()
    for eo in eo_list:
        with st.expander(f"📄 {eo.get('title')}"):
            st.write(eo.get('abstract'))
            st.link_button("View Official Document", eo.get('html_url'))

with tab3:
    st.subheader("⚖️ SCOTUS Docket")
    cases = fetch_scotus_cases()
    for case in cases:
        with st.expander(f"⚖️ {case.get('name')} [{case.get('docket_number')}]"):
            st.write(case.get('description', 'Summary pending.'))
            st.link_button("Oyez Details", f"https://www.oyez.org/cases/{case.get('term')}/{case.get('docket_number')}")

with tab4:
    if selection and selection.get("selection") and selection["selection"]["rows"]:
        idx = selection["selection"]["rows"][0]
        bill = st.session_state.bills_df.iloc[idx]
        
        st.header(bill['title'])
        st.metric("Bill Number", bill['number'], delta=bill['status'])
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("💰 Economic Impact")
            st.info(ai_analyze(bill['title'], bill['title'], "impact"))
        with c2:
            st.subheader("⚖️ Partisan Sentiment")
            st.info(ai_analyze(bill['title'], bill['title'], "sentiment"))
            
        st.divider()
        st.subheader("⚖️ Constitutional Compliance Check")
        if st.button("⚖️ Run Constitutional Audit"):
            with st.spinner("Analyzing legal precedent..."):
                st.warning(ai_analyze(bill['title'], bill['title'], "constitution"))
    else:
        st.info("👈 Select a bill in the **Legislation** tab to begin the deep dive.")

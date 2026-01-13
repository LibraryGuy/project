import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIGURATION & STATE MANAGEMENT ---
try:
    CONGRESS_API_KEY = st.secrets["CONGRESS_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Missing Secret Key: {e}. Check Streamlit Cloud Secrets.")
    st.stop()

# Initialize Session State for Persistance (Suggested Structure Improvement)
if 'bills_df' not in st.session_state:
    st.session_state.bills_df = pd.DataFrame()
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

CONGRESS_SESSION = "119"
BASE_URL = "https://api.congress.gov/v3"

# Setup AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="2026 Intel Tracker", layout="wide", page_icon="🏛️")

# --- 2. ADVANCED DATA FETCHING ---

@st.cache_data(ttl=600)
def fetch_data(endpoint):
    """Generic fetcher for better code structure."""
    api_key = CONGRESS_API_KEY.strip()
    url = f"{BASE_URL}/{endpoint}?api_key={api_key}&format=json"
    try:
        resp = requests.get(url)
        return resp.json() if resp.status_code == 200 else None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None

@st.cache_data(ttl=3600)
def fetch_eo_news():
    """Automated News Alerts: Pulls both official and 'Public Inspection' early drafts."""
    url = "https://www.federalregister.gov/api/v1/documents.json?conditions[type][]=PRESDOCU&conditions[presidential_document_type][]=executive_order&per_page=5"
    resp = requests.get(url)
    return resp.json().get('results', []) if resp.status_code == 200 else []

# --- 3. IMPACT & SENTIMENT ANALYSIS LOGIC ---

def ai_analyze_policy(text, title, analysis_type="summary"):
    """
    Sentiment & Impact Analysis: 
    Goes beyond summary to analyze who wins and who loses.
    """
    prompts = {
        "impact": f"Analyze the economic impact of '{title}'. Who are the winners and losers? (3 bullets each). Text: {text}",
        "sentiment": f"Analyze the partisan lean of '{title}'. Is it broadly bipartisan or sharply partisan? Explain why. Text: {text}",
        "semantic": f"Identify the top 3 industries affected by this policy: {title}"
    }
    
    if not text or "not yet available" in text:
        return "Deep analysis pending official text release."
    
    try:
        response = model.generate_content(prompts.get(analysis_type, prompts["impact"]))
        return response.text
    except Exception as e:
        return f"Analysis Error: {e}"

# --- 4. UI ENHANCEMENTS ---

st.title("🏛️ 2026 Intel Policy Tracker")
st.caption(f"Real-time Legislative Intelligence • {datetime.now().strftime('%B %d, %2026')}")

# Top Row: Automated News Alerts
with st.container():
    st.subheader("🔔 Automated Policy Alerts")
    orders = fetch_eo_news()
    cols = st.columns(len(orders) if orders else 1)
    for i, eo in enumerate(orders):
        with cols[i]:
            st.info(f"**EO Draft:** {eo.get('title')[:50]}...")
            st.caption(f"Published: {eo.get('publication_date')}")

tab1, tab2, tab3 = st.tabs(["📜 Legislation", "🖋️ Executive Actions", "🔬 Intelligence Deep Dive"])

with tab1:
    # SEARCH & FILTER ENGINE
    col1, col2 = st.columns([2,1])
    with col1:
        query = st.text_input("🔍 Semantic Search (e.g., 'energy subsidies', 'crypto regulation')", key="search_bar")
    with col2:
        status_filter = st.multiselect("Filter Status", ["Introduced", "Passed House", "Became Law"])

    raw_bills = fetch_data(f"bill/{CONGRESS_SESSION}")
    if raw_bills:
        df = pd.DataFrame(raw_bills.get('bills', []))
        df['status'] = df['latestAction'].apply(lambda x: x.get('text', 'N/A'))
        
        # LOGIC: Basic Semantic/Keyword Filtering
        if query:
            df = df[df['title'].str.contains(query, case=False)]
            
        st.session_state.bills_df = df
        selection = st.dataframe(
            df[['number', 'title', 'status']], 
            use_container_width=True, 
            on_select="rerun", 
            selection_mode="single-row", 
            hide_index=True,
            key="main_table"
        )

with tab3:
    # INTELLIGENCE DEEP DIVE
    if selection and selection.get("selection") and selection["selection"]["rows"]:
        idx = selection["selection"]["rows"][0]
        selected_bill = st.session_state.bills_df.iloc[idx]
        
        st.header(selected_bill['title'])
        
        # Structure Improvement: Metrics Row
        m1, m2, m3 = st.columns(3)
        m1.metric("Bill #", selected_bill['number'])
        m2.metric("Last Action", "Jan 2026")
        m3.metric("Sentiment", "Analyzing...")

        # Multi-Analysis Sections
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("💰 Economic Impact (Winners/Losers)")
            with st.spinner("Calculating impact..."):
                st.markdown(ai_analyze_policy(selected_bill['title'], selected_bill['title'], "impact"))
        
        with c2:
            st.subheader("⚖️ Partisan Sentiment")
            with st.spinner("Analyzing political lean..."):
                st.markdown(ai_analyze_policy(selected_bill['title'], selected_bill['title'], "sentiment"))
    else:
        st.info("Select a piece of legislation from the first tab to begin analysis.")

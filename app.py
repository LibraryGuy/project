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
model = genai.GenerativeModel('gemini-2.5-flash')

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

@st.cache_data(ttl=3600)
def fetch_executive_orders():
    """Fetches the latest 10 Executive Orders from the Federal Register."""
    url = "https://www.federalregister.gov/api/v1/documents.json?conditions[type][]=PRESDOCU&conditions[presidential_document_type][]=executive_order&per_page=10"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json().get('results', [])
        else:
            return []
    except Exception as e:
        st.error(f"Error fetching Executive Orders: {e}")
        return []

@st.cache_data(ttl=3600)
def fetch_scotus_cases():
    """Fetches recent Supreme Court cases from the Oyez API."""
    # Oyez uses year-based terms (e.g., 2025 for the 2025-2026 term)
    current_year = datetime.now().year if datetime.now().month >= 10 else datetime.now().year - 1
    url = f"https://api.oyez.org/cases?per_page=10&filter=term:{current_year}"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json()
        return []
    except:
        return []

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

tab1, tab2, tab3, tab4 = st.tabs(["📜 Legislation", "🖋️ Executive Actions", "⚖️ Supreme Court", "🔬 Intelligence Deep Dive"])

# --- 4. UI ENHANCEMENTS ---

st.title("🏛️ 2026 Intel Policy Tracker")
st.caption(f"Real-time Legislative Intelligence • {datetime.now().strftime('%B %d, %2026')}")

# Top Row: Automated News Alerts (Remains at the top)
with st.container():
    st.subheader("🔔 Automated Policy Alerts")
    orders = fetch_eo_news()
    if orders:
        cols = st.columns(len(orders))
        for i, eo in enumerate(orders):
            with cols[i]:
                st.info(f"**EO:** {eo.get('title')[:45]}...")
                st.caption(f"📅 {eo.get('publication_date')}")

# Update the Tab structure: 4 Tabs now
tab1, tab2, tab3, tab4 = st.tabs([
    "📜 Legislation", 
    "🖋️ Executive Actions", 
    "⚖️ Supreme Court", 
    "🔬 Intelligence Deep Dive"
])

# --- TAB 1: LEGISLATION ---
with tab1:
    col1, col2 = st.columns([2,1])
    with col1:
        query = st.text_input("🔍 Search Legislation", key="leg_search")
    
    raw_bills = fetch_data(f"bill/{CONGRESS_SESSION}")
    if raw_bills:
        df = pd.DataFrame(raw_bills.get('bills', []))
        df['status'] = df['latestAction'].apply(lambda x: x.get('text', 'N/A'))
        if query:
            df = df[df['title'].str.contains(query, case=False)]
        
        st.session_state.bills_df = df
        # We catch the selection here to use in Tab 4
        selection = st.dataframe(
            df[['number', 'title', 'status']], 
            use_container_width=True, 
            on_select="rerun", 
            selection_mode="single-row", 
            hide_index=True,
            key="main_table"
        )

# --- TAB 2: EXECUTIVE ACTIONS ---
with tab2:
    st.subheader("🖋️ Executive Orders library")
    eo_list = fetch_executive_orders() # Ensure this function is defined in Section 2
    if eo_list:
        for eo in eo_list:
            with st.expander(f"📄 {eo.get('title')}"):
                st.write(eo.get('abstract', 'No abstract available.'))
                st.link_button("View Official Document", eo.get('html_url'))

# --- TAB 3: SUPREME COURT (New Location) ---
with tab3:
    st.subheader("⚖️ Supreme Court Docket (2025-2026 Term)")
    scotus_cases = fetch_scotus_cases() # Ensure this function is defined in Section 2
    
    if scotus_cases:
        for case in scotus_cases:
            name = case.get('name', 'Unknown Case')
            docket = case.get('docket_number', 'N/A')
            # Facts are stored in 'description' in the summary API
            facts = case.get('description', 'Legal summary not yet provided.')
            
            with st.expander(f"⚖️ {name} [{docket}]"):
                st.markdown("**Facts of the Case:**")
                st.write(facts)
                
                # Dynamic link to Oyez website
                term_year = case.get('term', '2025')
                st.link_button("Read Full Legal Breakdown", f"https://www.oyez.org/cases/{term_year}/{docket}")
                
                if st.button(f"AI Legal Analysis: {docket}", key=f"sc_btn_{docket}"):
                    with st.spinner("AI is weighing the precedent..."):
                        sc_prompt = f"Explain this SCOTUS case to a non-lawyer. What is the constitutional question? Case: {name}. Facts: {facts}"
                        st.info(model.generate_content(sc_prompt).text)

# --- TAB 4: INTELLIGENCE DEEP DIVE ---
with tab4:
    # Check if anything was selected in Tab 1
    if selection and selection.get("selection") and selection["selection"]["rows"]:
        idx = selection["selection"]["rows"][0]
        selected_bill = st.session_state.bills_df.iloc[idx]
        
        st.header(selected_bill['title'])
        m1, m2 = st.columns(2)
        m1.metric("Bill #", selected_bill['number'])
        m2.metric("Latest Status", "Active" if "Introduced" not in selected_bill['status'] else "Introduced")

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("💰 Economic Impact")
            st.markdown(ai_analyze_policy(selected_bill['title'], selected_bill['title'], "impact"))
        with c2:
            st.subheader("⚖️ Partisan Sentiment")
            st.markdown(ai_analyze_policy(selected_bill['title'], selected_bill['title'], "sentiment"))
    else:
        st.info("👈 **Go to the 'Legislation' tab** and select a bill to view the Deep Dive analysis here.")

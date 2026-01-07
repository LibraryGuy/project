import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai

# --- 1. CONFIGURATION (Streamlit Secrets) ---
try:
    CONGRESS_API_KEY = st.secrets["CONGRESS_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Missing Secret Key: {e}. Please check your Streamlit Cloud Advanced Settings.")
    st.stop()

# Congress API defaults
CONGRESS_SESSION = "119"
BASE_URL = "https://api.congress.gov/v3"

# Setup Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="2026 Policy Tracker", layout="wide", page_icon="🏛️")

# --- 2. DATA FETCHING FUNCTIONS ---

@st.cache_data(ttl=600) # Caches data for 10 minutes to avoid hitting API limits
def fetch_recent_bills():
    url = f"{BASE_URL}/bill/{CONGRESS_SESSION}?api_key={CONGRESS_API_KEY}&format=json&limit=30"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json().get('bills', [])
        else:
            st.error(f"API Error: {resp.status_code}")
            return []
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return []

def get_on_demand_details(b_type, b_num):
    spon_url = f"{BASE_URL}/bill/{CONGRESS_SESSION}/{b_type}/{b_num}/sponsors?api_key={CONGRESS_API_KEY}&format=json"
    sum_url = f"{BASE_URL}/bill/{CONGRESS_SESSION}/{b_type}/{b_num}/summaries?api_key={CONGRESS_API_KEY}&format=json"
    details = {"party": "N/A", "summary": "Official summary text not yet available for this bill."}
    
    try:
        s_resp = requests.get(spon_url)
        sum_resp = requests.get(sum_url)
        
        if s_resp.status_code == 200:
            spons = s_resp.json().get('sponsors', [])
            if spons: details['party'] = spons[0].get('party', 'N/A')
        
        if sum_resp.status_code == 200:
            sums = sum_resp.json().get('summaries', [])
            if sums: details['summary'] = sums[0].get('text', details['summary'])
    except:
        pass
    return details

@st.cache_data(ttl=3600)
def fetch_executive_orders():
    url = "https://www.federalregister.gov/api/v1/documents.json?conditions[type][]=PRESDOCU&conditions[presidential_document_type][]=executive_order&per_page=10"
    try:
        resp = requests.get(url)
        return resp.json().get('results', []) if resp.status_code == 200 else []
    except:
        return []

# --- 3. AI LOGIC ---

def ai_explain(text, title):
    if not text or "not yet available" in text:
        return "I can't summarize this yet because the official text hasn't been provided by Congress."
    
    prompt = f"Explain this law or order in 3 simple, non-partisan bullet points for a high school student. Highlight why it matters. Title: {title}. Text: {text}"
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI Connection Error: {e}"

# --- 4. USER INTERFACE ---

st.title("🏛️ 2026 Legislative & Executive Tracker")
st.markdown("Track what's happening in DC in real-time. Select a bill to see AI summaries.")

tab1, tab2, tab3 = st.tabs(["📜 Proposed Laws", "🖋️ Executive Orders", "🔍 AI Deep Dive"])

# TAB 1: PROPOSED LAWS
with tab1:
    bills_data = fetch_recent_bills()
    if bills_data:
        df = pd.DataFrame(bills_data)
        # Extract status from the latestAction dictionary
        df['status'] = df['latestAction'].apply(lambda x: x.get('text') if x else "N/A")
        
        st.subheader("Latest Bills in Congress")
        # 'on_select="rerun"' allows Tab 3 to react when you click a row
        selection = st.dataframe(
            df[['number', 'title', 'status']], 
            use_container_width=True, 
            on_select="rerun", 
            selection_mode="single-row", 
            hide_index=True,
            key="bill_selector" 
        )
    else:
        st.warning("No bills found. This could be due to an API limit or a temporary connection issue.")

# TAB 2: EXECUTIVE ORDERS
with tab2:
    st.subheader("Latest Presidential Directives")
    orders = fetch_executive_orders()
    if orders:
        for eo in orders:
            with st.expander(f"{eo.get('title')}"):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.write(eo.get('abstract') if eo.get('abstract') else "No abstract available.")
                with col_b:
                    if st.button("AI Simplify", key=f"btn_{eo.get('document_number')}"):
                        st.session_state['eo_ai'] = ai_explain(eo.get('abstract'), eo.get('title'))
                
                if f"btn_{eo.get('document_number')}" in st.session_state:
                     # This displays the AI text if the specific button was clicked
                     pass # Handled by the button logic above
                st.link_button("View Official Document", eo.get('html_url'))
    else:
        st.info("No recent executive orders found.")

# TAB 3: AI DEEP DIVE
with tab3:
    # Check if a user has selected a row in Tab 1
    if selection and selection.selection.rows:
        row_idx = selection.selection.rows[0]
        bill_row = df.iloc[row_idx]
        
        st.header(f"Bill Detail: {bill_row['number']}")
        st.subheader(bill_row['title'])
        
        with st.spinner("AI is analyzing the legal language..."):
            extra = get_on_demand_details(bill_row['type'].lower(), bill_row['number'])
            summary_ai = ai_explain(extra['summary'], bill_row['title'])
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("### 🤖 AI 'Plain English' Breakdown")
            st.success(summary_ai)
            
            st.markdown("### Official Summary Text")
            st.write(extra['summary'])
        
        with col2:
            st.markdown("### Quick Stats")
            st.metric("Sponsoring Party", extra['party'])
            st.info(f"**Current Status:**\n{bill_row['status']}")
    else:
        st.info("👈 **Select a bill** in the 'Proposed Laws' tab first, then come back here for the AI analysis.")
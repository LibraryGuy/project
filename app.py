import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai

# --- 1. CONFIGURATION ---
try:
    CONGRESS_API_KEY = st.secrets["CONGRESS_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Missing Secret Key: {e}. Check Streamlit Cloud Secrets.")
    st.stop()

CONGRESS_SESSION = "119"
BASE_URL = "https://api.congress.gov/v3"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="2026 Policy Tracker", layout="wide", page_icon="🏛️")

# Initialize 'selection' to None so the app doesn't crash if API fails
selection = None

# --- 2. DATA FETCHING ---

@st.cache_data(ttl=600)
def fetch_recent_bills():
    # We strip spaces just in case they were pasted into Secrets accidentally
    api_key = CONGRESS_API_KEY.strip()
    url = f"{BASE_URL}/bill/{CONGRESS_SESSION}?api_key={api_key}&format=json&limit=30"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json().get('bills', [])
        else:
            # This will show you exactly what the API is complaining about
            st.error(f"API Error {resp.status_code}: Access Denied. Check your Congress API Key.")
            return []
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return []

# (Functions for details and AI remain the same as previous)
def get_on_demand_details(b_type, b_num):
    api_key = CONGRESS_API_KEY.strip()
    spon_url = f"{BASE_URL}/bill/{CONGRESS_SESSION}/{b_type}/{b_num}/sponsors?api_key={api_key}&format=json"
    sum_url = f"{BASE_URL}/bill/{CONGRESS_SESSION}/{b_type}/{b_num}/summaries?api_key={api_key}&format=json"
    details = {"party": "N/A", "summary": "Summary not yet available."}
    try:
        s_resp = requests.get(spon_url); sum_resp = requests.get(sum_url)
        if s_resp.status_code == 200:
            spons = s_resp.json().get('sponsors', [])
            if spons: details['party'] = spons[0].get('party', 'N/A')
        if sum_resp.status_code == 200:
            sums = sum_resp.json().get('summaries', [])
            if sums: details['summary'] = sums[0].get('text', details['summary'])
    except: pass
    return details

@st.cache_data(ttl=3600)
def fetch_executive_orders():
    url = "https://www.federalregister.gov/api/v1/documents.json?conditions[type][]=PRESDOCU&conditions[presidential_document_type][]=executive_order&per_page=10"
    try:
        resp = requests.get(url)
        return resp.json().get('results', []) if resp.status_code == 200 else []
    except: return []

def ai_explain(text, title):
    if not text or "not yet available" in text: return "Text pending."
    prompt = f"Explain this law in 3 simple bullet points. Title: {title}. Text: {text}"
    try:
        return model.generate_content(prompt).text
    except Exception as e: return f"AI Error: {e}"

# --- 3. UI ---

st.title("🏛️ 2026 Legislative Tracker")
tab1, tab2, tab3 = st.tabs(["📜 Proposed Laws", "🖋️ Executive Orders", "🔍 AI Deep Dive"])

with tab1:
    bills_data = fetch_recent_bills()
    if bills_data:
        df = pd.DataFrame(bills_data)
        df['status'] = df['latestAction'].apply(lambda x: x.get('text') if x else "N/A")
        selection = st.dataframe(
            df[['number', 'title', 'status']], 
            use_container_width=True, 
            on_select="rerun", 
            selection_mode="single-row", 
            hide_index=True,
            key="bill_selector" 
        )
    else:
        st.warning("No bills to display. Check API key status.")

with tab2:
    orders = fetch_executive_orders()
    for eo in orders:
        with st.expander(f"{eo.get('title')}"):
            st.write(eo.get('abstract'))
            st.link_button("View Document", eo.get('html_url'))

with tab3:
    # Now using a safe check for selection
    if selection and selection.get("selection") and selection["selection"]["rows"]:
        row_idx = selection["selection"]["rows"][0]
        bill_row = df.iloc[row_idx]
        with st.spinner("Analyzing..."):
            extra = get_on_demand_details(bill_row['type'].lower(), bill_row['number'])
            summary_ai = ai_explain(extra['summary'], bill_row['title'])
        st.header(bill_row['title'])
        st.success(summary_ai)
    else:
        st.info("Select a bill in the 'Proposed Laws' tab first.")
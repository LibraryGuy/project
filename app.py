import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai

# --- CONFIGURATION (Streamlit Secrets) ---
# These names must match EXACTLY what you typed on the left side in Streamlit Cloud
try:
    CONGRESS_API_KEY = st.secrets["CONGRESS_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Missing Secret Key: {e}. Please check your Streamlit Cloud Advanced Settings.")
    st.stop()

CONGRESS = "119"
BASE_URL = "https://api.congress.gov/v3"

# Setup Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
# Using 'gemini-1.5-flash' as it is currently the most stable for this use case
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="2026 Policy Tracker", layout="wide")

# --- DATA FETCHING ---
@st.cache_data(ttl=600)
def fetch_recent_bills():
    url = f"{BASE_URL}/bill/{CONGRESS}?api_key={CONGRESS_API_KEY}&format=json&limit=30"
    resp = requests.get(url)
    return resp.json().get('bills', []) if resp.status_code == 200 else []

def get_on_demand_details(b_type, b_num):
    spon_url = f"{BASE_URL}/bill/{CONGRESS}/{b_type}/{b_num}/sponsors?api_key={CONGRESS_API_KEY}&format=json"
    sum_url = f"{BASE_URL}/bill/{CONGRESS}/{b_type}/{b_num}/summaries?api_key={CONGRESS_API_KEY}&format=json"
    details = {"party": "N/A", "summary": "No summary text found."}
    
    s_resp = requests.get(spon_url); sum_resp = requests.get(sum_url)
    if s_resp.status_code == 200:
        spons = s_resp.json().get('sponsors', [])
        if spons: details['party'] = spons[0].get('party', 'N/A')
    if sum_resp.status_code == 200:
        sums = sum_resp.json().get('summaries', [])
        if sums: details['summary'] = sums[0].get('text', "Summary pending.")
    return details

@st.cache_data(ttl=3600)
def fetch_executive_orders():
    url = "https://www.federalregister.gov/api/v1/documents.json?conditions[type][]=PRESDOCU&conditions[presidential_document_type][]=executive_order&per_page=10"
    resp = requests.get(url)
    return resp.json().get('results', []) if resp.status_code == 200 else []

# --- AI SUMMARIZER ---
def ai_explain(text, title):
    if not text or "pending" in text:
        return "I can't summarize this yet because the official text hasn't been provided by Congress."
    
    prompt = f"Explain this law/order in 3 simple bullet points for a high school student. Title: {title}. Text: {text}"
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI Connection Error: {e}"

# --- UI ---
st.title("🏛️ 2026 Legislative & Executive Tracker")
tab1, tab2, tab3 = st.tabs(["📜 Proposed Laws", "🖋️ Executive Orders", "🔍 Deep Dive"])

with tab1:
    df = pd.DataFrame(fetch_recent_bills())
    if not df.empty:
        df['status'] = df['latestAction'].apply(lambda x: x.get('text') if x else "N/A")
        # selection_mode is for Streamlit 1.35+
        selection = st.dataframe(df[['number', 'title', 'status']], 
                                 use_container_width=True, 
                                 on_select="rerun", 
                                 selection_mode="single-row", 
                                 hide_index=True)

with tab2:
    st.subheader("Latest Presidential Directives")
    orders = fetch_executive_orders()
    for eo in orders:
        with st.expander(f"{eo.get('title')}"):
            if st.button("AI Simplify", key=eo.get('document_number')):
                st.info(ai_explain(eo.get('abstract'), eo.get('title')))
            else:
                st.write(eo.get('abstract'))
            st.link_button("Official Document", eo.get('html_url'))

with tab3:
    # Logic to handle bill selection from Tab 1
    if 'selection' in locals() and len(selection.selection.rows) > 0:
        row_idx = selection.selection.rows[0]
        bill_row = df.iloc[row_idx]
        
        with st.spinner("AI is reading the law..."):
            extra = get_on_demand_details(bill_row['type'].lower(), bill_row['number'])
            summary_ai = ai_explain(extra['summary'], bill_row['title'])
        
        st.header(bill_row['title'])
        st.subheader("🤖 AI 'Plain English' Explanation")
        st.success(summary_ai)
        
        st.subheader("Official Summary")
        st.write(extra['summary'])
    else:
        st.info("Select a bill in the 'Proposed Laws' tab to see the AI breakdown here.")
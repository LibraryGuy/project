import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai

# --- CONFIGURATION ---
CONGRESS_API_KEY = st.secrets["yFetrbibxRXTZbv9LWZ5Mc5jc7l9jwauH0I1l6QH"] 
GEMINI_API_KEY = st.secrets["AIzaSyCiHg3JbZ7EPY4Ds7tioegGJ6_lOPRVdz0"]
CONGRESS = "119"
BASE_URL = "https://api.congress.gov/v3"

# Setup Gemini
genai.configure(api_key=GEMINI_API_KEY)
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
# Updated Model Initialization
# Try 'gemini-1.5-flash-latest' which usually resolves 404 versioning errors
model = genai.GenerativeModel('gemini-2.5-flash')
def ai_explain(text, title):
    if not text or "pending" in text:
        return "I can't summarize this yet because the official text hasn't been provided by Congress."

    # Added a slightly more detailed prompt for better 2026-era results
    prompt = (
        f"You are a policy expert. Explain the following legislation in three clear, "
        f"non-partisan bullet points. Title: {title}. Text: {text}"
    )
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # If gemini-1.5-flash-latest still fails, let's try a fallback
        return f"AI Connection Error: {e}. Tip: Check if your API key has 'Generative AI' permissions enabled in AI Studio."

# --- UI ---
st.title("🏛️ 2026 Legislative & Executive Tracker")
tab1, tab2, tab3 = st.tabs(["📜 Proposed Laws", "🖋️ Executive Orders", "🔍 Deep Dive"])

with tab1:
    df = pd.DataFrame(fetch_recent_bills())
    if not df.empty:
        df['status'] = df['latestAction'].apply(lambda x: x.get('text') if x else "N/A")
        selection = st.dataframe(df[['number', 'title', 'status']], use_container_width=True, 
                                 on_select="rerun", selection_mode="single-row", hide_index=True)

with tab2:
    orders = fetch_executive_orders()
    for eo in orders:
        with st.expander(f"{eo.get('title')}"):
            if st.button("AI Simplify", key=eo.get('document_number')):
                st.info(ai_explain(eo.get('abstract'), eo.get('title')))
            else:
                st.write(eo.get('abstract'))
            st.link_button("Official Document", eo.get('html_url'))

with tab3:
    if 'selection' in locals() and len(selection.selection.rows) > 0:
        row = df.iloc[selection.selection.rows[0]]
        with st.spinner("AI is reading the law..."):
            extra = get_on_demand_details(row['type'].lower(), row['number'])
            summary_ai = ai_explain(extra['summary'], row['title'])
        
        st.header(row['title'])
        st.subheader("🤖 AI Explanation")
        st.success(summary_ai)
        st.subheader("Official Summary")
        st.write(extra['summary'])
    else:
        st.info("Select a bill in the first tab to see the AI breakdown here.")
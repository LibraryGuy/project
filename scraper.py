import requests

# CONFIGURATION
API_KEY = "yFetrbibxRXTZbv9LWZ5Mc5jc7l9jwauH0I1l6QH" 
CONGRESS = "119" # Current 2026 Congress
BASE_URL = "https://api.congress.gov/v3"

def get_recent_bills():
    url = f"{BASE_URL}/bill/{CONGRESS}?api_key={API_KEY}&format=json&limit=10"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get('bills', [])
    except Exception as e:
        print(f"Connection Error: {e}")
    return []

def get_bill_details(bill_type, bill_number):
    """Fetches summary and vote info for a specific bill."""
    # Summary Endpoint
    sum_url = f"{BASE_URL}/bill/{CONGRESS}/{bill_type}/{bill_number}/summaries?api_key={API_KEY}&format=json"
    
    print("\n--- BILL EXPLANATION ---")
    sum_resp = requests.get(sum_url)
    if sum_resp.status_code == 200:
        summaries = sum_resp.json().get('summaries', [])
        if summaries:
            print(summaries[0].get('text', 'No summary text found.'))
        else:
            print("Official summary is still being drafted by the Library of Congress.")
    
    # Simple Vote Check
    print("\n--- VOTE STATUS ---")
    # For a full vote tally, you'd check the 'actions' or 'recordedVotes' endpoints
    # Here we check the most recent action for a vote result
    action_url = f"{BASE_URL}/bill/{CONGRESS}/{bill_type}/{bill_number}/actions?api_key={API_KEY}&format=json"
    act_resp = requests.get(action_url)
    if act_resp.status_code == 200:
        actions = act_resp.json().get('actions', [])
        votes = [a for a in actions if "Vote" in a.get('text', '')]
        if votes:
            for v in votes:
                print(f"Result: {v.get('text')}")
        else:
            print("This bill has not reached a floor vote yet.")

def main_interface():
    print("Welcome to the 2026 Legislative Tracker")
    bills = get_recent_bills()
    
    if not bills:
        print("No bills found. Check your API key or connection.")
        return

    while True:
        print("\n--- RECENT PROPOSED LAWS ---")
        for i, bill in enumerate(bills):
            number = bill.get('number', 'N/A')
            title = bill.get('title', 'No Title')
            # Safely get status
            action_data = bill.get('latestAction')
            status = action_data.get('text', 'Status Pending') if action_data else "Status Pending"
            
            print(f"[{i+1}] Bill #{number}: {title[:70]}...")
            print(f"    Status: {status}")

        choice = input("\nEnter bill number to explain (or 'q' to quit): ")
        
        if choice.lower() == 'q':
            break
        
        if choice.isdigit() and 1 <= int(choice) <= len(bills):
            selected = bills[int(choice)-1]
            # Congress.gov API requires the 'type' (e.g., 'hr' or 's')
            b_type = selected.get('type', 'hr').lower()
            b_num = selected.get('number')
            get_bill_details(b_type, b_num)
            input("\nPress Enter to return to the list...")
        else:
            print("Invalid selection. Please try again.")

if __name__ == "__main__":
    main_interface()
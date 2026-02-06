import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime
import os
import json

# Configuration - Use the JSON API instead of parsing markdown
LISTINGS_JSON_URL = 'https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json'
SHEET_ID = os.environ.get('SHEET_ID')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_credentials():
    """Load credentials from environment variable"""
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS environment variable not set")
    
    creds_dict = json.loads(creds_json)
    return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

def fetch_listings():
    """Fetch the listings JSON from GitHub"""
    response = requests.get(LISTINGS_JSON_URL)
    response.raise_for_status()
    return response.json()

def parse_listings(data):
    """Parse the JSON data into internship listings"""
    internships = []
    
    for listing in data:
        # Only include active software engineering internships
        if listing.get('active', False) and listing.get('is_visible', True):
            company_name = listing.get('company_name', '')
            title = listing.get('title', '')
            locations = listing.get('locations', [])
            url = listing.get('url', '')
            date_posted_timestamp = listing.get('date_posted', '')
            
            # Convert Unix timestamp to readable date
            if date_posted_timestamp:
                try:
                    # Convert from milliseconds to seconds, then to datetime
                    date_posted = datetime.fromtimestamp(int(date_posted_timestamp) / 1000).strftime('%Y-%m-%d')
                except:
                    date_posted = 'Unknown'
            else:
                date_posted = 'Unknown'
            
            # Format locations
            if locations:
                location_str = ', '.join(locations[:3])  # First 3 locations
                if len(locations) > 3:
                    location_str += f' +{len(locations)-3} more'
            else:
                location_str = 'Not specified'
            
            internships.append({
                'company': company_name,
                'role': title,
                'location': location_str,
                'link': url,
                'original_date': date_posted
            })
    
    return internships

def update_sheet(internships):
    """Update Google Sheet with internship data"""
    creds = get_credentials()
    client = gspread.authorize(creds)
    
    # Open the sheet
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    # Get existing data (skip header)
    try:
        existing_data = sheet.get_all_values()[1:]
    except:
        existing_data = []
    
    # Create map of existing entries
    existing_map = {}
    for i, row in enumerate(existing_data):
        if len(row) >= 2 and row[0] and row[1]:
            key = f"{row[0]}_{row[1]}"
            existing_map[key] = {
                'row_index': i + 2,
                'date_added_to_sheet': row[4] if len(row) > 4 else '',
                'original_date': row[5] if len(row) > 5 else ''
            }
    
    # Prepare new data
    today = datetime.now().strftime('%Y-%m-%d')
    new_data = []
    
    for internship in internships:
        key = f"{internship['company']}_{internship['role']}"
        existing = existing_map.get(key)
        
        # Use existing dates if job was already in sheet, otherwise use today
        date_added = existing['date_added_to_sheet'] if existing else today
        original_date = existing['original_date'] if existing else internship['original_date']
        
        new_data.append([
            internship['company'],
            internship['role'],
            internship['location'],
            internship['link'],
            date_added,
            original_date,
            today
        ])
    
    # Clear existing data (keep header)
    if len(existing_data) > 0:
        try:
            sheet.delete_rows(2, len(existing_data) + 1)
        except:
            pass
    
    # Write new data
    if new_data:
        sheet.append_rows(new_data)
        print(f"Updated sheet with {len(new_data)} internships")
    else:
        print("No internships found")

def main():
    print("Fetching internship listings from JSON...")
    data = fetch_listings()
    print(f"Fetched {len(data)} total listings")
    
    print("\nParsing active internships...")
    internships = parse_listings(data)
    
    print(f"\nFound {len(internships)} active internships")
    
    if internships:
        print("Sample internships:")
        for i, internship in enumerate(internships[:5]):
            print(f"  {i+1}. {internship['company']} - {internship['role']}")
        
        print("\nUpdating Google Sheet...")
        update_sheet(internships)
        print("Done!")
    else:
        print("ERROR: No internships were found.")

if __name__ == '__main__':
    main()

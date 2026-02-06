import gspread
from google.oauth2.service_account import Credentials
import requests
import re
from datetime import datetime
import os
import json

# Configuration
GITHUB_RAW_URL = 'https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md'
SHEET_ID = os.environ.get('SHEET_ID')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_credentials():
    """Load credentials from environment variable"""
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS environment variable not set")
    
    creds_dict = json.loads(creds_json)
    return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

def fetch_readme():
    """Fetch the README content from GitHub"""
    response = requests.get(GITHUB_RAW_URL)
    response.raise_for_status()
    return response.text

def parse_markdown_table(content):
    """Parse the markdown table from README"""
    internships = []
    
    # Find the table section
    lines = content.split('\n')
    in_table = False
    
    for line in lines:
        line = line.strip()
        
        # Detect table start
        if '| Company | Role | Location |' in line:
            in_table = True
            continue
        
        # Skip separator line
        if in_table and '|---' in line:
            continue
        
        # Parse table rows
        if in_table and line.startswith('|'):
            # Stop at end of table (empty line or non-table content)
            if line.count('|') < 3:
                break
                
            cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove empty first/last
            
            if len(cells) >= 3:
                # Extract company and link
                company_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', cells[0])
                company = company_match.group(1) if company_match else cells[0]
                company_link = company_match.group(2) if company_match else ''
                
                # Extract role
                role = cells[1]
                
                # Extract location and application link
                location_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', cells[2])
                location = location_match.group(1) if location_match else cells[2]
                app_link = location_match.group(2) if location_match else ''
                
                # Use application link if available, otherwise company link
                final_link = app_link or company_link
                
                internships.append({
                    'company': company,
                    'role': role,
                    'location': location,
                    'link': final_link
                })
    
    return internships

def update_sheet(internships):
    """Update Google Sheet with internship data"""
    creds = get_credentials()
    client = gspread.authorize(creds)
    
    # Open the sheet
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    # Get existing data (skip header)
    existing_data = sheet.get_all_values()[1:]  # Skip header row
    
    # Create map of existing entries
    existing_map = {}
    for i, row in enumerate(existing_data):
        if len(row) >= 2:
            key = f"{row[0]}_{row[1]}"  # company_role
            existing_map[key] = {
                'row_index': i + 2,  # +2 for header and 0-indexing
                'date_posted': row[4] if len(row) > 4 else ''
            }
    
    # Prepare new data
    today = datetime.now().strftime('%Y-%m-%d')
    new_data = []
    
    for internship in internships:
        key = f"{internship['company']}_{internship['role']}"
        existing = existing_map.get(key)
        
        date_posted = existing['date_posted'] if existing else today
        
        new_data.append([
            internship['company'],
            internship['role'],
            internship['location'],
            internship['link'],
            date_posted,
            today
        ])
    
    # Clear existing data (keep header)
    if len(existing_data) > 0:
        sheet.delete_rows(2, len(existing_data) + 1)
    
    # Write new data
    if new_data:
        sheet.append_rows(new_data)
        print(f"Updated sheet with {len(new_data)} internships")
    else:
        print("No internships found")

def main():
    print("Fetching internship listings...")
    content = fetch_readme()
    
    print("Parsing markdown table...")
    internships = parse_markdown_table(content)
    
    print(f"Found {len(internships)} internships")
    
    print("Updating Google Sheet...")
    update_sheet(internships)
    
    print("Done!")

if __name__ == '__main__':
    main()

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
    
    # Split into lines
    lines = content.split('\n')
    in_table = False
    header_found = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Look for the table header - be flexible with spacing
        if not header_found and 'Company' in line and 'Role' in line and 'Location' in line and line.startswith('|'):
            header_found = True
            print(f"Found table header at line {i}: {line[:100]}")
            continue
        
        # Skip the separator line (the one with dashes)
        if header_found and not in_table and '---' in line:
            in_table = True
            print(f"Starting to parse table at line {i}")
            continue
        
        # Parse table rows
        if in_table and line.startswith('|'):
            # Split by pipe and clean up
            parts = line.split('|')
            # Remove empty first and last elements
            cells = [cell.strip() for cell in parts if cell.strip()]
            
            # Debug: print first few rows
            if len(internships) < 3:
                print(f"Row {i}: {len(cells)} cells - {cells[:3] if len(cells) >= 3 else cells}")
            
            # Need at least 3 columns: Company, Role, Location
            if len(cells) >= 3:
                # Extract company name and link from markdown [text](url)
                company_cell = cells[0]
                company_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', company_cell)
                if company_match:
                    company = company_match.group(1)
                    company_link = company_match.group(2)
                else:
                    company = company_cell
                    company_link = ''
                
                # Role (might also have markdown links)
                role_cell = cells[1]
                role_match = re.search(r'\[([^\]]+)\]', role_cell)
                role = role_match.group(1) if role_match else role_cell
                
                # Location and application link
                location_cell = cells[2]
                location_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', location_cell)
                if location_match:
                    location = location_match.group(1)
                    app_link = location_match.group(2)
                else:
                    location = location_cell
                    app_link = ''
                
                # Use app link if available, otherwise company link
                final_link = app_link or company_link
                
                # Skip if company is empty or looks like a header
                if company and company.lower() not in ['company', '---', '']:
                    internships.append({
                        'company': company,
                        'role': role,
                        'location': location,
                        'link': final_link
                    })
        
        # Stop if we hit an empty line or non-table content after table started
        elif in_table and (not line or not line.startswith('|')):
            print(f"End of table detected at line {i}")
            break
    
    print(f"Total internships parsed: {len(internships)}")
    if internships:
        print(f"First internship: {internships[0]}")
        print(f"Last internship: {internships[-1]}")
    
    return internships

def update_sheet(internships):
    """Update Google Sheet with internship data"""
    creds = get_credentials()
    client = gspread.authorize(creds)
    
    # Open the sheet
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    # Get existing data (skip header)
    try:
        existing_data = sheet.get_all_values()[1:]  # Skip header row
    except:
        existing_data = []
    
    # Create map of existing entries
    existing_map = {}
    for i, row in enumerate(existing_data):
        if len(row) >= 2 and row[0] and row[1]:  # Must have company and role
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
    print("Fetching internship listings...")
    content = fetch_readme()
    print(f"Fetched {len(content)} characters")
    
    print("\nParsing markdown table...")
    internships = parse_markdown_table(content)
    
    print(f"\nFound {len(internships)} internships")
    
    if internships:
        print("\nUpdating Google Sheet...")
        update_sheet(internships)
        print("Done!")
    else:
        print("ERROR: No internships were parsed. Check the table format.")

if __name__ == '__main__':
    main()

import pandas as pd
import argparse
from dotenv import load_dotenv

load_dotenv()

from app import app, db
from models import Website

def import_csv(csv_path):
    print(f"Reading CSV from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Normalize column names to lowercase to make it easier to match, or just check explicitly
    columns = df.columns.tolist()
    
    # Try to find mapping
    def get_col(candidates):
        for c in candidates:
            if c in columns:
                return c
        return None

    domain_col = get_col(['Domain', 'domain', 'url', 'URL'])
    title_col = get_col(['Title', 'title'])
    icp_col = get_col(['ICP', 'icp'])
    server_col = get_col(['Server', 'server'])
    screenshot_col = get_col(['Screenshot_Path', 'screenshot_path', 'screenshot', 'Screenshot'])

    if not domain_col:
        print("Error: Could not find 'Domain' column in CSV.")
        return

    websites_to_add = []
    
    # Process rows
    for index, row in df.iterrows():
        domain = str(row[domain_col]) if pd.notna(row[domain_col]) else ''
        if not domain:
            continue
            
        title = str(row[title_col]) if title_col and pd.notna(row[title_col]) else ''
        icp = str(row[icp_col]) if icp_col and pd.notna(row[icp_col]) else ''
        server = str(row[server_col]) if server_col and pd.notna(row[server_col]) else ''
        screenshot_path = str(row[screenshot_col]) if screenshot_col and pd.notna(row[screenshot_col]) else ''
        
        website = Website(
            domain=domain,
            title=title,
            icp=icp,
            server=server,
            screenshot_path=screenshot_path
        )
        websites_to_add.append(website)
        
    print(f"Found {len(websites_to_add)} websites. Inserting into database...")
    
    with app.app_context():
        db.create_all()
        # Clear existing? Or just append? Let's just append for now, but maybe check duplicates
        # For performance, bulk insert is better if it's large. Let's do simple add_all.
        # Check if already exists to avoid duplicates? The requirements didn't specify, but it's safer.
        # If it's a huge CSV, checking each is slow. Let's assume fresh DB or appending is fine.
        db.session.add_all(websites_to_add)
        db.session.commit()
        print("Import complete!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import websites from CSV')
    parser.add_argument('csv_path', type=str, help='Path to the CSV file')
    args = parser.parse_args()
    
    import_csv(args.csv_path)

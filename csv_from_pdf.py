import os
import csv
from datetime import datetime, timedelta
from PyPDF2 import PdfReader

CSV_DIR = "csv"

def sanitize_filename(text):
    return text.replace("/", "-").replace("\"", "").replace(",", "").replace(":", "").replace(" ", "_").replace("%", "percent")

def extract_date_from_text(text):
    import re
    match = re.search(r'w\.e\.f\.\s*(\d{1,2}\.\d{1,2}\.\d{4})', text)
    if match:
        try:
            date_obj = datetime.strptime(match.group(1), "%d.%m.%Y")
            return date_obj.strftime("%Y-%m-%d")
        except:
            pass
    return datetime.now().strftime("%Y-%m-%d")

def clean_description(desc):
    """Clean the description by removing unwanted patterns but preserving specifications"""
    import re
    
    # Remove rate patterns like "249500", "252000", etc. (5-6 digit numbers only)
    # But preserve important product specifications like "9.5", "61%", etc.
    desc = re.sub(r'\b\d{5,6}\b', '', desc)
    
    # Remove standalone large numbers that are clearly rates/prices (4+ digits)
    # But keep smaller numbers that are part of specifications
    desc = re.sub(r'\b\d{4,}\b(?=\s|$)', '', desc)
    
    # Remove extra whitespace
    desc = ' '.join(desc.split())
    
    # Remove trailing punctuation and whitespace, but preserve important punctuation within descriptions
    desc = desc.strip(' .-_')
    
    return desc

def extract_table_data(pdf_path):
    """Extract data from PDF with improved parsing and duplicate prevention"""
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join([page.extract_text() for page in reader.pages])
        lines = text.splitlines()
        
        data_rows = []
        seen_items = set()  # Track processed items to avoid duplicates
        current_date = extract_date_from_text(text)
        
        print(f"   📅 Extracted date: {current_date}")
        
        # Find the main table section
        table_started = False
        processed_numbers = set()
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Start processing after finding the products table
            if "PRODUCTS" in line.upper() and "Basic Price" in line:
                table_started = True
                continue
            
            # Stop processing if we hit notes or other sections
            if table_started and any(stop_word in line.upper() for stop_word in ["NOTE", "QUANTITY DISCOUNT", "FREIGHT CHARGES", "TAXES"]):
                break
            
            # Only process numbered items in the table section
            if table_started and line and len(line) > 2:
                import re
                number_match = re.match(r'^(\d+)\.\s+(.+)', line)
                
                if number_match:
                    item_number = number_match.group(1)
                    rest_of_line = number_match.group(2)
                    
                    # Skip if we already processed this item number
                    if item_number in processed_numbers:
                        continue
                    
                    processed_numbers.add(item_number)
                    parts = rest_of_line.split()
                    
                    if len(parts) >= 2:
                        try:
                            # Find the price (should be the last numeric value)
                            price_found = False
                            for j in range(len(parts) - 1, -1, -1):
                                try:
                                    price_str = parts[j].replace(",", "").replace("Rs/", "").replace("MT", "").strip()
                                    price_str = re.sub(r'[^\d]', '', price_str)
                                    
                                    if price_str:
                                        price = int(price_str)
                                        
                                        # Price should be reasonable for aluminum
                                        if price > 100000:
                                            desc_parts = parts[:j]
                                            desc = " ".join(desc_parts)
                                            desc = clean_description(desc)
                                            
                                            # Create unique key to avoid duplicates
                                            unique_key = f"{current_date}|{desc.lower()}"
                                            
                                            if len(desc) > 5 and unique_key not in seen_items:
                                                seen_items.add(unique_key)
                                                data_rows.append((current_date, desc, price))
                                                price_found = True
                                                print(f"   ✅ Item {item_number}: {desc} → ₹{price:,}")
                                                break
                                except (ValueError, IndexError):
                                    continue
                            
                            # If price not found on same line, check next line
                            if not price_found and i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                price_match = re.match(r'^(\d{6,})', next_line.replace(",", ""))
                                if price_match:
                                    price = int(price_match.group(1))
                                    desc = " ".join(parts)
                                    desc = clean_description(desc)
                                    
                                    unique_key = f"{current_date}|{desc.lower()}"
                                    if len(desc) > 5 and unique_key not in seen_items:
                                        seen_items.add(unique_key)
                                        data_rows.append((current_date, desc, price))
                                        print(f"   ✅ Item {item_number} (next line): {desc} → ₹{price:,}")
                                        
                        except Exception:
                            continue
            
            # Fallback: Also check for old-style numbered items (in case format changes)
            elif line and len(line) > 2 and line[0].isdigit() and '.' in line[:3]:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        price_found = False
                        for j in range(len(parts) - 1, -1, -1):
                            try:
                                price = int(parts[j].replace(",", ""))
                                if price > 100000:
                                    desc_parts = parts[1:j]
                                    desc = " ".join(desc_parts)
                                    desc = clean_description(desc)
                                    
                                    unique_key = f"{current_date}|{desc.lower()}"
                                    if len(desc) > 5 and unique_key not in seen_items:
                                        seen_items.add(unique_key)
                                        data_rows.append((current_date, desc, price))
                                        price_found = True
                                        print(f"   ✅ Fallback: {desc} → ₹{price:,}")
                                        break
                            except (ValueError, IndexError):
                                continue
                    except Exception:
                        continue
        
        print(f"   📊 Extracted {len(data_rows)} unique items")
        return data_rows
        
    except Exception as e:
        print(f"   ❌ Error reading PDF: {e}")
        return []

def append_to_csv(row):
    """Append data to CSV with duplicate checking"""
    date, desc, price = row
    filename = sanitize_filename(desc) + ".csv"
    csv_path = os.path.join(CSV_DIR, filename)
    os.makedirs(CSV_DIR, exist_ok=True)
    
    # Check if this exact date already exists
    if os.path.exists(csv_path):
        with open(csv_path, "r", newline="") as f:
            existing_content = f.read()
            if date in existing_content:
                print(f"   ⏭️ Skipping {desc} - data for {date} already exists")
                return
    
    # If file doesn't exist, create with header
    if not os.path.exists(csv_path):
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Product", "Price"])
    
    # Append new data
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([date, desc, price])
    
    print(f"   ✅ Added to {filename}: {date}, {desc}, ₹{price:,}")

def find_todays_pdf():
    """Find today's PDF file with fallback options"""
    today = datetime.now()
    
    # Try different date ranges (today, yesterday, last 3 days)
    for days_back in range(4):
        check_date = today - timedelta(days=days_back)
        
        # Different folder patterns
        possible_folders = [
            os.path.join("Downloads", check_date.strftime("%Y"), check_date.strftime("%b")),
            os.path.join("Downloads", check_date.strftime("%Y-%m")),
            "Downloads",
            "."
        ]
        
        # Different filename patterns
        possible_filenames = [
            f"Hindalco_Circular_{check_date.strftime('%d_%b_%y')}.pdf",
            f"primary-ready-reckoner-{check_date.strftime('%d-%B-%Y').lower()}.pdf",
            f"primary-ready-reckoner-{check_date.strftime('%d-%b-%Y').lower()}.pdf"
        ]
        
        for folder in possible_folders:
            if os.path.exists(folder):
                for filename in possible_filenames:
                    pdf_path = os.path.join(folder, filename)
                    if os.path.exists(pdf_path):
                        return pdf_path
                
                # Search for any recent Hindalco PDF
                try:
                    for file in os.listdir(folder):
                        if (file.lower().startswith('hindalco') or 
                            file.lower().startswith('primary-ready-reckoner')) and \
                           file.lower().endswith('.pdf'):
                            return os.path.join(folder, file)
                except OSError:
                    continue
    
    return None

def process_pdf(pdf_path):
    """Process PDF and update CSV files"""
    print(f"🔄 Processing: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF file not found: {pdf_path}")
        return False
    
    extracted_rows = extract_table_data(pdf_path)
    
    if not extracted_rows:
        print("⚠️ No data extracted from PDF")
        return False
    
    print(f"📊 Processing {len(extracted_rows)} extracted rows")
    
    for row in extracted_rows:
        date, desc, price = row
        append_to_csv(row)
    
    return True

if __name__ == "__main__":
    print("🚀 Starting daily CSV update...")
    
    # Find today's PDF
    pdf_path = find_todays_pdf()
    
    if pdf_path:
        print(f"🔍 Found PDF: {pdf_path}")
        success = process_pdf(pdf_path)
        
        if success:
            print(f"✅ Successfully processed and updated CSVs from: {pdf_path}")
            print(f"📁 CSV files updated in: {CSV_DIR}")
        else:
            print("❌ Failed to process PDF")
            exit(1)
    else:
        print("❌ No recent Hindalco PDF found")
        print("🔍 Searching for PDFs...")
        
        # Debug: List available files
        for search_dir in ["Downloads", "."]:
            if os.path.exists(search_dir):
                print(f"📁 Files in {search_dir}:")
                try:
                    for file in os.listdir(search_dir):
                        if file.lower().endswith('.pdf'):
                            print(f"   - {file}")
                except OSError as e:
                    print(f"   Error: {e}")
        
        exit(1)

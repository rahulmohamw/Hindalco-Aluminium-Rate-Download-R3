import os
import csv
from datetime import datetime
from PyPDF2 import PdfReader
import glob

CSV_DIR = "csv"

def sanitize_filename(text):
    """Clean filename for CSV creation"""
    return text.replace("/", "-").replace("\"", "").replace(",", "").replace(":", "").replace(" ", "_").replace("%", "percent")

def extract_date_from_text(text):
    """Extract date from PDF text with multiple patterns"""
    import re
    
    # Pattern 1: w.e.f. DD.MM.YYYY
    match = re.search(r'w\.e\.f\.\s*(\d{1,2}\.\d{1,2}\.\d{4})', text)
    if match:
        try:
            date_obj = datetime.strptime(match.group(1), "%d.%m.%Y")
            return date_obj.strftime("%Y-%m-%d")
        except:
            pass
    
    # Pattern 2: w.e.f. DD.MM.YYYY (with different spacing)
    match = re.search(r'w\.e\.f\.\s*(\d{1,2})\.(\d{1,2})\.(\d{4})', text)
    if match:
        try:
            day, month, year = match.groups()
            date_obj = datetime(int(year), int(month), int(day))
            return date_obj.strftime("%Y-%m-%d")
        except:
            pass
    
    # Pattern 3: Extract from filename if present
    # primary-ready-reckoner-11-july-2025.pdf -> 2025-07-11
    filename_patterns = [
        r'(\d{1,2})-(\w+)-(\d{4})',
        r'(\d{1,2})_(\w+)_(\d{2,4})',
        r'(\d{1,2})\.(\d{1,2})\.(\d{4})'
    ]
    
    return None

def extract_date_from_filename(filename):
    """Extract date from filename patterns"""
    import re
    
    # Pattern: primary-ready-reckoner-11-july-2025.pdf
    match = re.search(r'(\d{1,2})-(\w+)-(\d{4})', filename.lower())
    if match:
        day, month_name, year = match.groups()
        month_mapping = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
        
        month_num = month_mapping.get(month_name.lower())
        if month_num:
            try:
                date_obj = datetime(int(year), month_num, int(day))
                return date_obj.strftime("%Y-%m-%d")
            except:
                pass
    
    # Pattern: Hindalco_Circular_11_Jul_25.pdf
    match = re.search(r'(\d{1,2})_(\w+)_(\d{2})', filename)
    if match:
        day, month_name, year = match.groups()
        # Convert 2-digit year to 4-digit
        year_full = 2000 + int(year) if int(year) < 50 else 1900 + int(year)
        
        month_mapping = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        month_num = month_mapping.get(month_name.lower())
        if month_num:
            try:
                date_obj = datetime(year_full, month_num, int(day))
                return date_obj.strftime("%Y-%m-%d")
            except:
                pass
    
    return datetime.now().strftime("%Y-%m-%d")

def clean_description(desc):
    """Clean the description by removing unwanted patterns but preserving specifications"""
    import re
    
    # Remove rate patterns like "249500", "252000", etc. (5-6 digit numbers only)
    desc = re.sub(r'\b\d{5,6}\b', '', desc)
    
    # Remove standalone large numbers that are clearly rates/prices (4+ digits)
    # But keep smaller numbers that are part of specifications
    desc = re.sub(r'\b\d{4,}\b(?=\s|$)', '', desc)
    
    # Remove extra whitespace
    desc = ' '.join(desc.split())
    
    # Remove trailing punctuation and whitespace
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
        
        # Try to extract date from text first, then from filename
        current_date = extract_date_from_text(text)
        if not current_date:
            current_date = extract_date_from_filename(os.path.basename(pdf_path))
        
        print(f"   📅 Extracted date: {current_date}")
        
        # Find the main table section by looking for "PRODUCTS" header
        table_started = False
        processed_numbers = set()  # Track item numbers already processed
        
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
                # Look for numbered items (1., 2., 3., etc.) at start of line
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
                    
                    if len(parts) >= 2:  # At least description and price
                        try:
                            # Find the price (should be the last numeric value on the line)
                            price_found = False
                            for j in range(len(parts) - 1, -1, -1):
                                try:
                                    price_str = parts[j].replace(",", "").replace("Rs/", "").replace("MT", "").strip()
                                    # Remove any trailing text like "Nil", "Rs/", etc.
                                    price_str = re.sub(r'[^\d]', '', price_str)
                                    
                                    if price_str:  # Only if we have digits
                                        price = int(price_str)
                                        
                                        # Price should be reasonable
                                        if price > 100000:  # Aluminum prices are typically > 100k
                                            # Everything before the price is description
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
                                # Look for standalone price on next line
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
                                        
                        except Exception as e:
                            continue
        
        print(f"   📊 Extracted {len(data_rows)} unique items")
        return data_rows
        
    except Exception as e:
        print(f"   ❌ Error reading PDF: {e}")
        return []

def create_csv_file(product_name, data_points):
    """Create or update CSV file for a product with duplicate removal"""
    filename = sanitize_filename(product_name) + ".csv"
    csv_path = os.path.join(CSV_DIR, filename)
    os.makedirs(CSV_DIR, exist_ok=True)
    
    # Remove duplicates based on date and price
    unique_data = {}
    for date, desc, price in data_points:
        key = f"{date}|{price}"
        if key not in unique_data:
            unique_data[key] = (date, desc, price)
    
    # Convert back to list and sort by date
    final_data = list(unique_data.values())
    final_data.sort(key=lambda x: x[0])
    
    # Write CSV with headers
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Product", "Price"])
        for date, desc, price in final_data:
            writer.writerow([date, desc, price])
    
    print(f"   💾 Created: {filename} with {len(final_data)} unique data points")

def process_all_pdfs():
    """Process all PDF files and create consolidated CSV files"""
    
    # Find all PDF files in Downloads directory
    pdf_patterns = [
        "Downloads/**/*.pdf",
        "Downloads/**/**/*.pdf",
        "*.pdf"
    ]
    
    all_pdfs = []
    for pattern in pdf_patterns:
        all_pdfs.extend(glob.glob(pattern, recursive=True))
    
    # Filter for Hindalco-related PDFs
    hindalco_pdfs = []
    for pdf in all_pdfs:
        filename = os.path.basename(pdf).lower()
        if any(keyword in filename for keyword in ['hindalco', 'primary-ready-reckoner', 'circular']):
            hindalco_pdfs.append(pdf)
    
    print(f"🔍 Found {len(hindalco_pdfs)} Hindalco PDF files:")
    for pdf in hindalco_pdfs:
        print(f"   📄 {pdf}")
    
    if not hindalco_pdfs:
        print("❌ No Hindalco PDF files found!")
        return
    
    # Dictionary to collect data by product
    product_data = {}
    
    # Process each PDF
    for pdf_path in hindalco_pdfs:
        print(f"\n🔄 Processing: {pdf_path}")
        extracted_rows = extract_table_data(pdf_path)
        
        for date, desc, price in extracted_rows:
            if desc not in product_data:
                product_data[desc] = []
            product_data[desc].append((date, desc, price))
    
    # Create CSV files for each product
    print(f"\n📊 Creating CSV files for {len(product_data)} products:")
    for product_name, data_points in product_data.items():
        create_csv_file(product_name, data_points)
    
    print(f"\n✅ Bulk extraction completed!")
    print(f"📁 CSV files created in: {CSV_DIR}")
    print(f"📈 Total products: {len(product_data)}")

if __name__ == "__main__":
    print("🚀 Starting bulk PDF to CSV extraction...")
    process_all_pdfs()

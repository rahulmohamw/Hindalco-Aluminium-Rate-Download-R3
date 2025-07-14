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
    """Extract data from PDF with improved parsing"""
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join([page.extract_text() for page in reader.pages])
        lines = text.splitlines()
        
        data_rows = []
        
        # Try to extract date from text first, then from filename
        current_date = extract_date_from_text(text)
        if not current_date:
            current_date = extract_date_from_filename(os.path.basename(pdf_path))
        
        print(f"   📅 Extracted date: {current_date}")
        
        # Parse lines for numbered items
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Look for numbered items (1., 2., 3., etc.)
            if line and len(line) > 2 and line[0].isdigit() and '.' in line[:3]:
                parts = line.split()
                
                if len(parts) >= 3:  # Minimum: number, description, price
                    try:
                        # Try to find the price (last numeric value)
                        price_found = False
                        for j in range(len(parts) - 1, -1, -1):
                            try:
                                # Clean the potential price string
                                price_str = parts[j].replace(",", "").replace("Rs/", "").replace("MT", "").strip()
                                price = int(price_str)
                                
                                # Price should be reasonable (> 1000 for these items)
                                if price > 1000:
                                    # Everything between item number and price is description
                                    desc_parts = parts[1:j]
                                    desc = " ".join(desc_parts)
                                    desc = clean_description(desc)
                                    
                                    # Skip if description is too short or contains only numbers
                                    if len(desc) > 3 and not desc.isdigit():
                                        data_rows.append((current_date, desc, price))
                                        price_found = True
                                        print(f"   ✅ Found: {desc} → ₹{price:,}")
                                        break
                            except (ValueError, IndexError):
                                continue
                        
                        # If we couldn't find a price in the current line, check next line
                        if not price_found and i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            next_parts = next_line.split()
                            
                            if next_parts:
                                try:
                                    price_str = next_parts[0].replace(",", "").replace("Rs/", "").replace("MT", "").strip()
                                    price = int(price_str)
                                    if price > 1000:
                                        desc = " ".join(parts[1:])
                                        desc = clean_description(desc)
                                        
                                        if len(desc) > 3 and not desc.isdigit():
                                            data_rows.append((current_date, desc, price))
                                            print(f"   ✅ Found (next line): {desc} → ₹{price:,}")
                                except (ValueError, IndexError):
                                    continue
                                    
                    except Exception as e:
                        continue
        
        return data_rows
        
    except Exception as e:
        print(f"   ❌ Error reading PDF: {e}")
        return []

def create_csv_file(product_name, data_points):
    """Create or update CSV file for a product"""
    filename = sanitize_filename(product_name) + ".csv"
    csv_path = os.path.join(CSV_DIR, filename)
    os.makedirs(CSV_DIR, exist_ok=True)
    
    # Sort data points by date
    data_points.sort(key=lambda x: x[0])
    
    # Write CSV with headers
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Product", "Price"])
        for date, desc, price in data_points:
            writer.writerow([date, desc, price])
    
    print(f"   💾 Created: {filename} with {len(data_points)} data points")

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

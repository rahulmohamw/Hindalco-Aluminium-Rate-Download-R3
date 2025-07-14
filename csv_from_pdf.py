import os
import csv
from datetime import datetime
from PyPDF2 import PdfReader

CSV_DIR = "csv"

def sanitize_filename(text):
    return text.replace("/", "-").replace("\"", "").replace(",", "").replace(":", "").replace(" ", "_")

def extract_date_from_text(text):
    import re
    match = re.search(r'w\.e\.f\.\s*(\d{2}\.\d{2}\.\d{4})', text)
    if match:
        date_obj = datetime.strptime(match.group(1), "%d.%m.%Y")
        return date_obj.strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")

def clean_description(desc):
    """Clean the description by removing common unwanted patterns"""
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
    reader = PdfReader(pdf_path)
    text = "\n".join([page.extract_text() for page in reader.pages])
    lines = text.splitlines()
    
    data_rows = []
    current_date = extract_date_from_text(text)
    
    # More precise line parsing
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Look for numbered items (1., 2., 3., etc.)
        if line and line[0].isdigit() and '.' in line[:3]:
            parts = line.split()
            
            if len(parts) >= 3:  # Minimum: number, description, price
                try:
                    # Try to find the price (last numeric value)
                    price_found = False
                    for j in range(len(parts) - 1, -1, -1):
                        try:
                            price = int(parts[j].replace(",", ""))
                            # Price should be reasonable (> 1000 for these items)
                            if price > 1000:
                                # Everything between item number and price is description
                                desc_parts = parts[1:j]
                                desc = " ".join(desc_parts)
                                desc = clean_description(desc)
                                
                                # Skip if description is too short or contains only numbers
                                if len(desc) > 5 and not desc.isdigit():
                                    data_rows.append((current_date, desc, price))
                                    price_found = True
                                    break
                        except (ValueError, IndexError):
                            continue
                    
                    # If we couldn't find a price in the current line, 
                    # check if it's split across lines
                    if not price_found and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        next_parts = next_line.split()
                        
                        if next_parts:
                            try:
                                price = int(next_parts[0].replace(",", ""))
                                if price > 1000:
                                    desc = " ".join(parts[1:])
                                    desc = clean_description(desc)
                                    
                                    if len(desc) > 5 and not desc.isdigit():
                                        data_rows.append((current_date, desc, price))
                            except (ValueError, IndexError):
                                continue
                                
                except Exception as e:
                    continue
    
    return data_rows

def append_to_csv(row):
    date, desc, price = row
    filename = sanitize_filename(desc) + ".csv"
    csv_path = os.path.join(CSV_DIR, filename)
    os.makedirs(CSV_DIR, exist_ok=True)
    
    # Skip if this date already exists
    if os.path.exists(csv_path):
        with open(csv_path, "r", newline="") as f:
            if any(date in line for line in f):
                return
    
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([date, desc, price])

def process_pdf(pdf_path):
    extracted_rows = extract_table_data(pdf_path)
    print(f"📊 Extracted {len(extracted_rows)} rows from PDF")
    
    for row in extracted_rows:
        date, desc, price = row
        print(f"   📝 {desc} → {price}")
        append_to_csv(row)

if __name__ == "__main__":
    today = datetime.now()
    pdf_folder = os.path.join("Downloads", today.strftime("%Y"), today.strftime("%b"))
    
    # Target Hindalco circular files with format: Hindalco_Circular_DD_Mon_YY.pdf
    pdf_filename = f"Hindalco_Circular_{today.strftime('%d_%b_%y')}.pdf"
    pdf_path = os.path.join(pdf_folder, pdf_filename)
    print(f"🔍 Looking for: {pdf_path}")
    
    if os.path.exists(pdf_path):
        process_pdf(pdf_path)
        print(f"✅ Processed and updated CSVs from: {pdf_path}")
    else:
        print("❌ PDF not found. Skipping.")
        
        # Debug: List available files in the directory
        if os.path.exists(pdf_folder):
            print(f"📁 Files in {pdf_folder}:")
            for file in os.listdir(pdf_folder):
                if file.endswith('.pdf') and 'Hindalco_Circular' in file:
                    print(f"   - {file}")
        else:
            print(f"📁 Directory {pdf_folder} does not exist")
            
        exit(0)  # Graceful exit with no error

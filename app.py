import streamlit as st
from PIL import Image
# import pytesseract
# import easyocr
import requests
import re
import mysql.connector

# Path to Tesseract executable (change if using Linux/Mac)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# DB connection
def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="pass@123",
        database="Experiment10"
    )

def extract_text_from_image(image_path):
    api_key = "K86782520788957"  # Replace with your key from ocr.space
    with open(image_path, 'rb') as f:
        r = requests.post(
            'https://api.ocr.space/parse/image',
            files={'filename': f},
            data={'apikey': api_key, 'language': 'eng'},
        )
    result = r.json()
    if result['IsErroredOnProcessing']:
        return ""
    return result['ParsedResults'][0]['ParsedText']


def extract_fields(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    # Extract email
    email_pattern = r"\b[\w\.-]+@[\w\.-]+\.\w+\b"
    email = re.findall(email_pattern, text)
    
    # Extract phone numbers (improved pattern)
    phone_pattern = r"(?:\+\d{1,3}[-.\s]?)?\(?(?:\d{3}|\d{4})\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
    phone = re.findall(phone_pattern, text)
    
    # Common designation keywords
    designation_keywords = [
        'manager', 'director', 'ceo', 'cto', 'cfo', 'president', 'vice president', 'vp',
        'senior', 'junior', 'lead', 'head', 'chief', 'executive', 'officer',
        'engineer', 'developer', 'analyst', 'consultant', 'specialist', 'coordinator',
        'supervisor', 'administrator', 'assistant', 'associate', 'partner',
        'founder', 'owner', 'proprietor', 'md', 'gm', 'sales', 'marketing',
        'hr', 'finance', 'operations', 'business', 'account', 'project'
    ]
    
    # Company keywords/suffixes
    company_keywords = [
        'ltd', 'limited', 'inc', 'incorporated', 'corp', 'corporation', 'llc',
        'company', 'co', 'enterprises', 'solutions', 'services', 'systems',
        'technologies', 'tech', 'group', 'international', 'global', 'pvt',
        'private', 'public', 'industries', 'associates', 'partners', 'consulting',
        'consultancy', 'firm', 'agency', 'organization', 'org'
    ]
    
    # Address keywords
    address_keywords = [
        'street', 'st', 'road', 'rd', 'avenue', 'ave', 'lane', 'ln', 'drive', 'dr',
        'plaza', 'square', 'park', 'place', 'floor', 'suite', 'unit', 'apt',
        'building', 'tower', 'complex', 'city', 'state', 'zip', 'pincode',
        'pin', 'postal', 'code', 'area', 'sector', 'block', 'house', 'no'
    ]
    
    # Initialize extracted data
    extracted_data = {
        "name": "",
        "email": email[0] if email else "",
        "phone": phone[0] if phone else "",
        "company": "",
        "designation": "",
        "address": ""
    }
    
    # Separate lines into categories
    name_candidates = []
    company_candidates = []
    designation_candidates = []
    address_candidates = []
    
    for line in lines:
        line_lower = line.lower()
        
        # Skip lines with email or phone (already extracted)
        if re.search(email_pattern, line) or re.search(phone_pattern, line):
            continue
            
        # Check if line contains designation keywords
        if any(keyword in line_lower for keyword in designation_keywords):
            designation_candidates.append(line)
        
        # Check if line contains company keywords
        elif any(keyword in line_lower for keyword in company_keywords):
            company_candidates.append(line)
            
        # Check if line contains address keywords or numbers (likely address)
        elif (any(keyword in line_lower for keyword in address_keywords) or 
              re.search(r'\d+', line) or len(line) > 30):
            address_candidates.append(line)
            
        # Lines with proper case and reasonable length (likely names)
        elif (len(line.split()) <= 4 and len(line) > 2 and 
              any(c.isupper() for c in line) and not line.isupper()):
            name_candidates.append(line)
        
        # Short lines in all caps might be company names
        elif line.isupper() and len(line.split()) <= 3:
            company_candidates.append(line)
    
    # Extract name (prefer first candidate, or first non-company line)
    if name_candidates:
        extracted_data["name"] = name_candidates[0]
    elif lines and not any(keyword in lines[0].lower() for keyword in company_keywords):
        extracted_data["name"] = lines[0]
    
    # Extract company
    if company_candidates:
        extracted_data["company"] = company_candidates[0]
    
    # Extract designation
    if designation_candidates:
        extracted_data["designation"] = designation_candidates[0]
    
    # Extract address (combine multiple address lines)
    if address_candidates:
        extracted_data["address"] = " | ".join(address_candidates[:3])  # Limit to 3 lines
    
    # Fallback logic: if we couldn't identify company but have unassigned lines
    remaining_lines = [line for line in lines if line not in [
        extracted_data["name"], extracted_data["company"], 
        extracted_data["designation"]] + address_candidates]
    
    # If no company found, check remaining lines
    if not extracted_data["company"] and remaining_lines:
        for line in remaining_lines:
            if len(line.split()) <= 4 and not any(keyword in line.lower() for keyword in address_keywords):
                extracted_data["company"] = line
                break
    
    # Clean up extracted data
    for key in extracted_data:
        if isinstance(extracted_data[key], str):
            extracted_data[key] = extracted_data[key].strip()
    
    return extracted_data

def insert_into_db(data):
    conn = connect_db()
    cursor = conn.cursor()
    sql = """INSERT INTO visiting_cards (name, email, phone, company, designation, address)
             VALUES (%s, %s, %s, %s, %s, %s)"""
    values = (data['name'], data['email'], data['phone'], data['company'], data['designation'], data['address'])
    cursor.execute(sql, values)
    conn.commit()
    conn.close()

# Streamlit UI
st.title("Visiting Card Extractor - MySQL Integration")

# Add preview option
preview_mode = st.checkbox("Preview extracted data before saving to database")

uploaded_files = st.file_uploader("Upload visiting cards", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        st.subheader(f"Processing: {file.name}")
        
        # Save uploaded file temporarily
        with open("temp.jpg", "wb") as f:
            f.write(file.read())
        
        # Extract text and fields
        text = extract_text_from_image("temp.jpg")
        data = extract_fields(text)
        
        # Show extracted text for debugging
        with st.expander("View extracted text"):
            st.text(text)
        
        # Display extracted data
        st.write("**Extracted Information:**")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Name:** {data['name']}")
            st.write(f"**Email:** {data['email']}")
            st.write(f"**Phone:** {data['phone']}")
        
        with col2:
            st.write(f"**Company:** {data['company']}")
            st.write(f"**Designation:** {data['designation']}")
            st.write(f"**Address:** {data['address']}")
        
        if preview_mode:
            # Allow user to edit before saving
            with st.form(f"edit_form_{file.name}"):
                data['name'] = st.text_input("Name", value=data['name'])
                data['email'] = st.text_input("Email", value=data['email'])
                data['phone'] = st.text_input("Phone", value=data['phone'])
                data['company'] = st.text_input("Company", value=data['company'])
                data['designation'] = st.text_input("Designation", value=data['designation'])
                data['address'] = st.text_area("Address", value=data['address'])
                
                if st.form_submit_button("Save to Database"):
                    insert_into_db(data)
                    st.success(f"✅ Saved: {data['name']}")
        else:
            # Auto-save to database
            insert_into_db(data)
            st.success(f"✅ Auto-saved: {data['name']}")
        
        st.divider()

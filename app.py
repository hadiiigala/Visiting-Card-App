import os
import streamlit as st
from PIL import Image
from google.cloud import vision
import io
import re
import sqlite3
import pandas as pd

# ✅ Set path to Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\tikona capital\VisitingCardExtractor\vision_credentials.json"

# ---------------- DB Setup ----------------
def connect_db():
    conn = sqlite3.connect("visiting_cards.db")
    conn.execute('''CREATE TABLE IF NOT EXISTS visiting_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        phone TEXT,
        company TEXT,
        designation TEXT,
        address TEXT
    )''')
    return conn

# ---------------- OCR with Vision API ----------------
def extract_text_from_image(image_path):
    client = vision.ImageAnnotatorClient()
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# ---------------- Field Extraction ----------------
def extract_fields(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    email_pattern = r"\b[\w\.-]+@[\w\.-]+\.\w+\b"
    phone_pattern = r"(?:\+\d{1,3}[-.\s]?)?\(?(?:\d{3}|\d{4})\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
    email = re.findall(email_pattern, text)
    phone = re.findall(phone_pattern, text)

    designation_keywords = ['manager', 'developer', 'director', 'engineer', 'analyst', 'ceo', 'cto', 'cfo']
    company_keywords = ['ltd', 'pvt', 'inc', 'solutions', 'tech', 'systems', 'group']
    address_keywords = ['road', 'street', 'avenue', 'lane', 'city', 'state', 'zip', 'pincode']

    data = {
        "name": "",
        "email": email[0] if email else "",
        "phone": phone[0] if phone else "",
        "company": "",
        "designation": "",
        "address": ""
    }

    name_candidates, company_candidates, designation_candidates, address_candidates = [], [], [], []

    for line in lines:
        lower = line.lower()
        if re.search(email_pattern, line) or re.search(phone_pattern, line):
            continue
        if any(k in lower for k in designation_keywords):
            designation_candidates.append(line)
        elif any(k in lower for k in company_keywords):
            company_candidates.append(line)
        elif any(k in lower for k in address_keywords) or re.search(r'\d+', line):
            address_candidates.append(line)
        elif len(line.split()) <= 4 and any(c.isupper() for c in line):
            name_candidates.append(line)

    if name_candidates: data['name'] = name_candidates[0]
    if company_candidates: data['company'] = company_candidates[0]
    if designation_candidates: data['designation'] = designation_candidates[0]
    if address_candidates: data['address'] = " | ".join(address_candidates[:3])

    return data

# ---------------- DB Operations ----------------
def insert_into_db(data):
    conn = connect_db()
    cursor = conn.cursor()
    sql = "INSERT INTO visiting_cards (name, email, phone, company, designation, address) VALUES (?, ?, ?, ?, ?, ?)"
    values = (data['name'], data['email'], data['phone'], data['company'], data['designation'], data['address'])
    cursor.execute(sql, values)
    conn.commit()
    conn.close()

def get_all_data():
    conn = connect_db()
    df = pd.read_sql_query("SELECT * FROM visiting_cards", conn)
    conn.close()
    return df

def delete_by_name(name):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM visiting_cards WHERE name = ?", (name,))
    conn.commit()
    conn.close()

# ---------------- Streamlit UI ----------------
st.set_page_config(layout="wide")
st.title("📇 Visiting Card Extractor (Vision API + SQLite)")

tab1, tab2, tab3 = st.tabs(["📤 Upload Cards", "📋 View & Delete", "✍️ Manual Entry"])

# ---- Tab 1: Upload and Auto Extract ----
with tab1:
    preview_mode = st.checkbox("Preview extracted data before saving")
    uploaded_files = st.file_uploader("Upload visiting cards", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

    if uploaded_files:
        for file in uploaded_files:
            st.subheader(f"Processing: {file.name}")
            with open("temp.jpg", "wb") as f:
                f.write(file.read())

            text = extract_text_from_image("temp.jpg")
            data = extract_fields(text)

            with st.expander("📄 Extracted Text"):
                st.text(text)

            st.write("**🧾 Extracted Information:**")
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
                with st.form(f"form_{file.name}"):
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
                insert_into_db(data)
                st.success(f"✅ Auto-saved: {data['name']}")

# ---- Tab 2: View & Delete Entries ----
with tab2:
    st.subheader("📋 All Saved Visiting Cards")
    df = get_all_data()
    st.dataframe(df, use_container_width=True)

    names = df['name'].tolist()
    selected_name = st.selectbox("Select a name to delete", ["-- Select --"] + names)

    if selected_name != "-- Select --":
        if st.button("❌ Delete Selected Entry"):
            delete_by_name(selected_name)
            st.success(f"Deleted record for: {selected_name}")
            st.rerun()

# ---- Tab 3: Manual Entry ----
with tab3:
    st.subheader("✍️ Add New Visiting Card Manually")
    with st.form("manual_entry"):
        name = st.text_input("Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        company = st.text_input("Company")
        designation = st.text_input("Designation")
        address = st.text_area("Address")
        if st.form_submit_button("Save to Database"):
            insert_into_db({
                "name": name,
                "email": email,
                "phone": phone,
                "company": company,
                "designation": designation,
                "address": address
            })
            st.success("✅ Entry added manually!")


import os
import requests
from openai import OpenAI
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# -------------------------------
# ENV Variables
# -------------------------------
ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI()


# -------------------------------
# ZOHO ACCESS TOKEN
# -------------------------------
def generate_access_token():
    url = "https://accounts.zoho.in/oauth/v2/token"
    params = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }

    r = requests.post(url, data=params)
    data = r.json()

    if "access_token" not in data:
        print("❌ Error generating access token:", data)
        return None

    return data["access_token"]


# -------------------------------
#  CREATE ZOHO LEAD
# -------------------------------
def create_zoho_lead(phone, name, message, matter_type, urgency):
    access_token = generate_access_token()
    if not access_token:
        return {"error": "zoho_auth_failed"}

    url = "https://www.zohoapis.in/crm/v2/Leads"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

    data = {
        "data": [{
            "Last_Name": name if name else "WhatsApp User",
            "Phone": phone,
            "Description": message,
            "Matter_Type": matter_type,
            "Urgency": urgency
        }],
        "trigger": ["workflow"]
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()


# -------------------------------
#  CREATE ZOHO TASK
# -------------------------------
def create_zoho_task(lead_id, summary):
    access_token = generate_access_token()
    if not access_token:
        return {"error": "zoho_auth_failed"}

    url = "https://www.zohoapis.in/crm/v2/Tasks"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

    data = {
        "data": [{
            "Subject": "Follow-up Needed",
            "Description": summary,
            "Status": "Not Started",
            "What_Id": lead_id
        }]
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()


# -------------------------------
# SUMMARIZE MESSAGE (AI)
# -------------------------------
def summarize_message(text):
    try:
        prompt = f"Summarize this client's message in 1 sentence:\n\n{text}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        summary = resp.choices[0].message.content
        return summary
    except Exception as e:
        print("AI summary failed:", e)
        return text[:150]


# -------------------------------
# DETECT FOLLOW-UP NEED
# -------------------------------
def needs_followup(text):
    t = text.lower()
    keywords = ["call", "follow", "remind", "tomorrow", "urgent", "meet", "appointment"]

    for k in keywords:
        if k in t:
            return True

    return False


# -------------------------------
# CLASSIFY MESSAGE TYPE
# -------------------------------
def classify_message(text):
    t = text.lower()

    if "draft" in t or "deed" in t or "agreement" in t:
        return "Drafting", "High"

    if "notice" in t:
        return "Notice", "High"

    if "opinion" in t or "advice" in t:
        return "Opinion", "Medium"

    if "case" in t or "court" in t or "legal" in t:
        return "Litigation", "High"

    return "General", "Low"


# -------------------------------
# WHATSAPP VERIFY WEBHOOK
# -------------------------------
@app.get("/webhook")
async def verify(request: Request):
    params = dict(request.query_params)

    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return params.get("hub.challenge")

    return "Invalid verify token"


# -------------------------------
# WHATSAPP MESSAGE RECEIVER
# -------------------------------
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    body = await request.json()

    # Extract message safely
    try:
        msg = body["entry"][0]["changes"][0]["value"]["messages"][0]
        if msg.get("type") != "text" or "text" not in msg:
            return {"status": "ignored"}
        text = msg["text"]["body"]
        phone = msg["from"]
    except (KeyError, IndexError, TypeError):
        return {"status": "ignored"}

    print("📩 WhatsApp Message Received:", text)

    # 1. Classify message
    matter_type, urgency = classify_message(text)

    # 2. Create / update lead
    lead_result = create_zoho_lead(
        phone=phone,
        name=f"WhatsApp_{phone}",
        message=text,
        matter_type=matter_type,
        urgency=urgency
    )

    # Extract Lead ID
    try:
        lead_id = lead_result["data"][0]["details"]["id"]
    except (KeyError, IndexError, TypeError):
        lead_id = None

    # 3. Summarize message
    summary = summarize_message(text)

    # 4. Follow-up detection
    if needs_followup(text) and lead_id:
        task_result = create_zoho_task(lead_id, summary)
        task_status = "Task Created"
    else:
        task_status = "No Task Needed"

    return {
        "status": "processed",
        "summary": summary,
        "followup": task_status,
        "matter_type": matter_type,
        "urgency": urgency,
        "lead": lead_result
    }


# -------------------------------
# TEST ROUTES
# -------------------------------
@app.get("/")
def home():
    return {"message": "WhatsApp → Zoho CRM Automation Active"}

@app.get("/test_create_lead")
def test_create():
    return create_zoho_lead(
        phone="919999999999",
        name="Test User",
        message="Example WhatsApp message",
        matter_type="Drafting",
        urgency="High"
    )

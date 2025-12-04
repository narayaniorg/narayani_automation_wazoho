import requests
import os
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")


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
        print("Error generating access token:", data)
        return None

    return data["access_token"]

def create_zoho_lead(phone, name, message, matter_type, urgency):
    access_token = generate_access_token()

    url = "https://www.zohoapis.in/crm/v2/Leads"

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }

    # Body for Zoho Lead
    data = {
        "data": [
            {
                "Last_Name": name if name else "WhatsApp User",
                "Phone": phone,
                "Description": message,
                "Matter_Type": matter_type,
                "Urgency": urgency
            }
        ],
        "trigger": ["workflow"]
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()

@app.get("/test_create_lead")
def test_create():
    result = create_zoho_lead(
        phone="919999999999",
        name="Test User",
        message="Example WhatsApp message",
        matter_type="Drafting",
        urgency="High"
    )
    return result


@app.get("/")
def root():
    access_token = generate_access_token()
    return {"access_token": access_token}

import gspread
import os
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Any

load_dotenv()

def update_crm_tool(data: Dict[str, Any]) -> str:
    """
    Push sales call analysis to Google Sheets CRM
    
    Args:
        data: Dictionary containing CRM fields
        
    Returns:
        Success or error message
    """
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        
        # Check if service account file exists
        service_account_path = "service_account.json"
        if not os.path.exists(service_account_path):
            return "❌ CRM Update Failed: service_account.json not found. Please add your Google Service Account credentials."
        
        creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_name = os.getenv("CRM_SHEET_NAME", "Sales_CRM_Production")
        
        try:
            sheet = client.open(sheet_name).sheet1
        except gspread.SpreadsheetNotFound:
            return f"❌ CRM Update Failed: Spreadsheet '{sheet_name}' not found. Please create it or update CRM_SHEET_NAME in .env"
        
        # Prepare row data
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get("prospect_name", ""),
            data.get("company_name", ""),
            data.get("summary", ""),
            data.get("pain_points", ""),
            str(data.get("sentiment_score", "")),
            data.get("next_steps", ""),
            str(data.get("call_quality", "")),
            data.get("follow_up_email", "")
        ]
        
        # Add header if sheet is empty
        if sheet.row_count == 0 or not sheet.row_values(1):
            headers = [
                "Timestamp", "Prospect Name", "Company", "Summary", 
                "Pain Points", "Sentiment Score", "Next Steps", 
                "Call Quality", "Follow-up Email"
            ]
            sheet.append_row(headers)
        
        sheet.append_row(row)
        return f"✅ CRM Updated: {data.get('prospect_name', 'Unknown')} from {data.get('company_name', 'Unknown')}"
        
    except Exception as e:
        return f"❌ CRM Update Failed: {str(e)}"


def push_to_crm(analysis: Dict[str, Any]) -> str:
    """Alias for update_crm_tool for backwards compatibility"""
    return update_crm_tool(analysis)
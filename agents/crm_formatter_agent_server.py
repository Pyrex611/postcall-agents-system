from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool
from tools.google_sheets_crm import update_crm_tool
from datetime import datetime

crm_formatter_agent = LlmAgent(
    name="CRMFormatterAgent",
    model=Gemini(model="gemini-2.5-flash-lite"),
    instruction="""
    You are a CRM Data Formatter.
    
    Take the {structured_data} from AnalystAgent and {quality_metrics} from QualityAgent.
    
    Format the data for CRM insertion:
    1. Combine pain_points list into a comma-separated string
    2. Combine next_steps list into a comma-separated string
    3. Include all required fields
    4. Use the update_crm_tool to save the formatted data
    
    The tool expects a dictionary with these keys:
    - prospect_name
    - company_name
    - summary
    - pain_points (string)
    - sentiment_score
    - next_steps (string)
    - call_quality (from quality_metrics)
    - follow_up_email
    """,
    tools=[FunctionTool(update_crm_tool)],
    output_key="crm_status"
)
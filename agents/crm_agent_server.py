from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from tools.google_sheets_crm import update_crm_tool

crm_agent = LlmAgent(
    name="CRMAgent",
    model=Gemini(model="gemini-1.5-flash"),
    instruction="Take the {structured_data} and use the update_crm_tool to save it.",
    tools=[FunctionTool(update_crm_tool)],
    output_key="crm_log_status"
)
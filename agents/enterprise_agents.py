from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool

# --- 1. Methodology-Aware Analyst ---
def get_analyst_agent(methodology="General"):
    """
    Dynamically generates an analyst agent instruction based on the user's
    selected sales methodology (MEDDIC, SPIN, BANT, etc.)
    """
    base_instruction = """
    You are a Senior Sales Data Analyst.
    Analyze the following transcript.
    """
    
    methodology_instructions = {
        "MEDDIC": """
        Evaluate the call specifically against the MEDDIC framework:
        - Metrics: What is the economic impact?
        - Economic Buyer: Who controls the budget?
        - Decision Criteria: Technical/financial requirements?
        - Decision Process: How do they buy?
        - Identify Pain: What is the problem?
        - Champion: Who is selling for us inside?
        """,
        "SPIN": """
        Identify the SPIN components used:
        - Situation questions asked
        - Problem questions asked
        - Implication questions asked
        - Need-Payoff questions asked
        """,
        "BANT": """
        Extract BANT details:
        - Budget
        - Authority
        - Need
        - Timeline
        """
    }
    
    instruction = base_instruction + methodology_instructions.get(methodology, "") + """
    \nExtract the prospect name, company, sentiment score (1-10), and next steps.
    """
    
    return LlmAgent(
        name=f"AnalystAgent_{methodology}",
        model=Gemini(model="gemini-2.5-flash-lite"),
        instruction=instruction,
        output_key="structured_data"
    )

# --- 2. Security-Conscious Email Reviewer ---
email_reviewer_agent = LlmAgent(
    name="EmailReviewer",
    model=Gemini(model="gemini-2.5-flash-lite"),
    instruction="""
    Review the draft email. 
    SECURITY CHECK: Ensure no PII (SSNs, Credit Cards) or confidential internal pricing is leaked.
    TONE CHECK: Ensure the tone matches a senior consultant (helpful, not pushy).
    """,
    output_key="follow_up_email"
)

# --- 3. Dynamic Advisor ---
advisor_agent = LlmAgent(
    name="StrategicAdvisor",
    model=Gemini(model="gemini-2.5-flash-lite"),
    instruction="""
    Based on the identified pain points and the methodology gaps (e.g., missing Economic Buyer),
    recommend 3 specific actions to advance the deal.
    """,
    output_key="strategic_advice"
)
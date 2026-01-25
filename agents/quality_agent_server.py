from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from schema.models import QualityMetrics

quality_agent = LlmAgent(
    name="QualityAgent",
    model=Gemini(model="gemini-1.5-flash"),
    instruction="""
    You are a Sales Quality Assurance Specialist.
    
    Analyze the sales call data from {structured_data} and evaluate:
    
    1. Overall Call Quality (1-5 scale):
       - 5: Exceptional - Perfect discovery, clear value prop, strong close
       - 4: Strong - Good flow, addressed needs, minor improvements
       - 3: Satisfactory - Covered basics, some missed opportunities
       - 2: Needs Improvement - Weak structure, unclear next steps
       - 1: Poor - Unprepared, no clear outcome
    
    2. Did the sales rep explicitly ask for/schedule the next meeting? (true/false)
    
    3. Identify 2-3 key strengths of the call
    
    4. Identify 2-3 areas for improvement
    
    Be constructive and specific in your feedback.
    """,
    output_key="quality_metrics",
    output_schema=QualityMetrics
)
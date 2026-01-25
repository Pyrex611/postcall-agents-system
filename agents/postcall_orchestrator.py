from google.adk.agents import SequentialAgent
from agents.analyst_agent_server import analyst_agent
from agents.quality_agent_server import quality_agent
from agents.crm_formatter_agent_server import crm_formatter_agent
from agents.advisor_agent_server import advisor_agent

postcall_orchestrator = SequentialAgent(
    name="PostCallOrchestrator",
    sub_agents=[
        analyst_agent,      # Step 1: Analyze call and extract insights
        quality_agent,      # Step 2: Assess call quality
        crm_formatter_agent,  # Step 3: Format and save to CRM
        advisor_agent       # Step 4: Generate strategic recommendations
    ],
    description="Complete pipeline for AI-powered sales call intelligence and CRM automation"
)
import asyncio
import uuid
from agents.enterprise_agents import get_analyst_agent, email_reviewer_agent, advisor_agent
from services.crm_integration import CRMFactory
from core.database import db
from google.adk.runners import InMemoryRunner
from google.adk.agents import SequentialAgent

async def process_call_job(job_id: str, transcript: str, org_config: dict):
    """
    This is the Worker Process. In production, this runs on a separate server.
    """
    try:
        print(f"⚙️ [Worker] Starting Job {job_id} for {org_config['name']}...")
        db.update_job(job_id, "PROCESSING")

        # 1. Build the Pipeline Dynamic to the Methodology
        methodology = org_config.get('methodology', 'GENERIC')
        analyst = get_analyst_agent(methodology)
        
        # 2. Run ADK Pipeline
        pipeline = SequentialAgent(
            name="EnterprisePipeline",
            sub_agents=[analyst, advisor_agent, email_reviewer_agent]
        )
        
        runner = InMemoryRunner(agent=pipeline)
        events = await runner.run_debug(transcript)
        
        # 3. Extract Results (Logic similar to original PoC but cleaner)
        final_state = {}
        for event in events:
            ev_dict = event.model_dump() if hasattr(event, 'model_dump') else {}
            actions = ev_dict.get('actions', {})
            delta = actions.get('state_delta', {})
            if delta:
                final_state.update(delta)
        
        # 4. Perform CRM Sync (The "Side Effect")
        crm_adapter = CRMFactory.get_adapter(org_config['crm_type'])
        sync_msg = crm_adapter.sync_data(
            final_state.get('structured_data', {}), 
            org_config['crm_config']
        )
        
        # 5. Save to DB
        db.update_job(
            job_id, 
            "COMPLETED", 
            result=final_state,
            crm_status=sync_msg
        )
        print(f"✅ [Worker] Job {job_id} Completed.")
        
    except Exception as e:
        print(f"❌ [Worker] Job {job_id} Failed: {str(e)}")
        db.update_job(job_id, "FAILED", crm_status=str(e))

def submit_job(org_id: int, rep_name: str, transcript: str):
    """
    Public API to submit a job
    """
    job_id = str(uuid.uuid4())
    db.create_job(job_id, org_id, rep_name, transcript)
    
    # In a real app, this would be celery.delay()
    # For this script, we will run it shortly in the Streamlit loop
    return job_id
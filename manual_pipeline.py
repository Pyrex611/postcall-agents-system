"""
Manual agent pipeline implementation as fallback
Use this if Google ADK Runner API issues persist
"""

import asyncio
from typing import Dict, Any
from datetime import datetime
from agents.analyst_agent_server import analyst_agent
from agents.quality_agent_server import quality_agent
from agents.advisor_agent_server import advisor_agent
from tools.google_sheets_crm import update_crm_tool

from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search, AgentTool, ToolContext
from google.adk.code_executors import BuiltInCodeExecutor



async def run_manual_pipeline(user_input: str) -> Dict[str, Any]:
    """
    Manually chain the agents without using SequentialAgent
    This is a fallback if InMemoryRunner has API issues
    
    Args:
        user_input: The sales call transcript or audio file path
        
    Returns:
        Dictionary with all agent outputs
    """
    
    result = {
        'input': user_input,
        'structured_data': {},
        'quality_metrics': {},
        'crm_status': '',
        'strategic_advice': '',
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # Step 1: Analyst Agent - Extract insights
        print("Running Analyst Agent...")
        analyst_runner = InMemoryRunner(agent=analyst_agent)
        analyst_response = await analyst_runner.run_debug(user_input)
        
        # Parse the response - ADK agents typically return structured data
        if hasattr(analyst_response, 'structured_data'):
            result['structured_data'] = analyst_response.structured_data
        elif isinstance(analyst_response, dict):
            result['structured_data'] = analyst_response.get('structured_data', analyst_response)
        else:
            result['structured_data'] = analyst_response
            
        print(f"✅ Analyst Agent complete")
        
    except Exception as e:
        print(f"❌ Analyst Agent failed: {e}")
        result['error'] = f"Analyst Agent: {str(e)}"
        return result
    
    try:
        # Step 2: Quality Agent - Assess call quality
        print("Running Quality Agent...")
        quality_runner = InMemoryRunner(agent=quality_agent)
        quality_response = await quality_runner.run_debug(result['structured_data'])
        
        if hasattr(quality_response, 'quality_metrics'):
            result['quality_metrics'] = quality_response.quality_metrics
        elif isinstance(quality_response, dict):
            result['quality_metrics'] = quality_response.get('quality_metrics', quality_response)
        else:
            result['quality_metrics'] = quality_response
            
        print(f"✅ Quality Agent complete")
        
    except Exception as e:
        print(f"⚠️  Quality Agent failed: {e}")
        # Continue even if quality fails
        result['quality_metrics'] = {
            'call_quality_score': 3,
            'asked_for_meeting': False,
            'strengths': [],
            'improvements': []
        }
    
    try:
        # Step 3: CRM Formatter - Save to CRM
        print("Running CRM Formatter...")
        
        # Format data for CRM
        crm_data = {
            'prospect_name': result['structured_data'].get('prospect_name', ''),
            'company_name': result['structured_data'].get('company_name', ''),
            'summary': result['structured_data'].get('summary', ''),
            'pain_points': ', '.join(result['structured_data'].get('pain_points', [])),
            'sentiment_score': result['structured_data'].get('sentiment_score', 0),
            'next_steps': ', '.join(result['structured_data'].get('next_steps', [])),
            'call_quality': result['quality_metrics'].get('call_quality_score', 0),
            'follow_up_email': result['structured_data'].get('follow_up_email', '')
        }
        
        # Call the CRM tool directly
        crm_status = update_crm_tool(crm_data)
        result['crm_status'] = crm_status
        
        print(f"✅ CRM update complete: {crm_status}")
        
    except Exception as e:
        print(f"⚠️  CRM update failed: {e}")
        result['crm_status'] = f"❌ CRM Update Failed: {str(e)}"
    
    try:
        # Step 4: Advisor Agent - Generate recommendations
        print("Running Advisor Agent...")
        
        # Combine data for advisor
        advisor_input = {
            'structured_data': result['structured_data'],
            'quality_metrics': result['quality_metrics']
        }
        
        advisor_runner = InMemoryRunner(agent=advisor_agent)
        advisor_response = await advisor_runner.run_debug(advisor_input)
        
        if hasattr(advisor_response, 'strategic_advice'):
            result['strategic_advice'] = advisor_response.strategic_advice
        elif isinstance(advisor_response, dict):
            result['strategic_advice'] = advisor_response.get('strategic_advice', advisor_response)
        else:
            result['strategic_advice'] = str(advisor_response)
            
        print(f"✅ Advisor Agent complete")
        
    except Exception as e:
        print(f"⚠️  Advisor Agent failed: {e}")
        result['strategic_advice'] = "Recommendations unavailable due to processing error."
    
    return result


def run_manual_pipeline_sync(user_input: str) -> Dict[str, Any]:
    """
    Synchronous wrapper for the manual pipeline
    Use this from Streamlit if async causes issues
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_manual_pipeline(user_input))
        return result
    finally:
        loop.close()


if __name__ == "__main__":
    # Test the manual pipeline
    test_input = """
    Rep: Hi Sarah, thanks for taking the time today.
    
    Prospect: Hi, I've been looking at your solution. We need something to handle our data pipeline issues.
    
    Rep: Can you tell me more about your current challenges?
    
    Prospect: We process 2TB daily and our ETL takes 12 hours. We need real-time insights.
    
    Rep: Our platform can reduce that to 90 minutes. Would you like a demo?
    
    Prospect: Yes, let's schedule one for next Tuesday.
    """
    
    print("Testing manual pipeline...")
    print("="*60)
    
    result = run_manual_pipeline_sync(test_input)
    
    print("\n" + "="*60)
    print("RESULTS:")
    print("="*60)
    
    import json
    print(json.dumps(result, indent=2, default=str))
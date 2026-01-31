import streamlit as st
import asyncio
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from agents.postcall_orchestrator import postcall_orchestrator
from google.adk.runners import InMemoryRunner

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="SalesOps AI Assistant",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .stAlert {
        margin-top: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'results' not in st.session_state:
    st.session_state.results = None

# Header
st.markdown('<div class="main-header">🚀 SalesOps AI Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Post-Call Analysis & CRM Automation</div>', unsafe_allow_html=True)

# Sidebar - Configuration & Info
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Check environment setup
    st.subheader("System Status")
    
    api_key = os.getenv("GOOGLE_API_KEY")
    crm_sheet = os.getenv("CRM_SHEET_NAME")
    service_account_exists = os.path.exists("service_account.json")
    
    if api_key and api_key != "your_gemini_api_key":
        st.success("✅ Google API Key configured")
    else:
        st.error("❌ Google API Key missing")
        st.info("Add GOOGLE_API_KEY to your .env file")
    
    if service_account_exists:
        st.success("✅ Service Account configured")
    else:
        st.warning("⚠️ service_account.json not found")
        st.info("CRM updates will be disabled until you add your Google Service Account credentials")
    
    st.info(f"📊 CRM Sheet: {crm_sheet}")
    
    st.divider()
    
    st.subheader("📖 How It Works")
    st.markdown("""
    1. **Upload** your sales call recording or paste transcript
    2. **AI Analysis** extracts key insights
    3. **Quality Review** assesses call performance
    4. **CRM Update** saves data automatically
    5. **Strategic Advice** provides next best actions
    """)
    
    st.divider()
    
    st.subheader("🎯 Features")
    st.markdown("""
    - ✨ Multi-modal input (Audio/Text)
    - 🧠 AI-powered analysis
    - 📊 Call quality scoring
    - 📧 Auto-generated follow-ups
    - 💾 Automated CRM updates
    - 🎯 Strategic recommendations
    """)

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📥 Input")
    
    # Input mode selection
    input_mode = st.radio(
        "Select Input Type:",
        ["Text Transcript", "Audio File"],
        horizontal=True,
        help="Choose how you want to provide the sales call data"
    )
    
    user_input = None
    
    if input_mode == "Audio File":
        st.info("🎵 Audio transcription feature coming soon! For now, please use text transcript.")
        uploaded_file = st.file_uploader(
            "Upload Recording",
            type=["mp3", "wav", "m4a"],
            help="Supported formats: MP3, WAV, M4A"
        )
        if uploaded_file:
            st.audio(uploaded_file)
            user_input = f"[Audio file: {uploaded_file.name}]"
            st.warning("Note: Audio transcription is not yet implemented. Please use text transcript instead.")
    else:
        user_input = st.text_area(
            "Paste Call Transcript:",
            height=300,
            placeholder="""Example:
            
Rep: Hi John, thanks for taking the time today. How are you?

Prospect: Good, thanks for reaching out. I've been looking into solutions for our data pipeline issues.

Rep: Great! Can you tell me more about the challenges you're facing?

Prospect: Well, we're processing about 2TB of data daily, and our current ETL process is taking too long...

[Continue with your transcript]
            """,
            help="Paste the full transcript of your sales call here"
        )

with col2:
    st.subheader("🎬 Actions")
    
    # Process button
    process_btn = st.button(
        "🚀 Analyze Call",
        type="primary",
        disabled=st.session_state.processing or not user_input or (input_mode == "Audio File" and uploaded_file),
        use_container_width=True
    )
    
    if st.session_state.results:
        if st.button("🔄 Clear Results", use_container_width=True):
            st.session_state.results = None
            st.rerun()
    
    st.divider()
    
    # Quick stats if results exist
    if st.session_state.results:
        st.metric("Sentiment Score", f"{st.session_state.results.get('sentiment_score', 'N/A')}/10")
        st.metric("Call Quality", f"{st.session_state.results.get('call_quality', 'N/A')}/5")
user_input = "
Sales Call Transcript - Demo

Rep: Good morning Sarah! This is Mike from DataFlow Solutions. Thanks so much for taking the time to speak with me today. How are you doing?

Sarah Chen: Hi Mike, I'm doing well, thanks. I've been looking forward to this call. We've been having some challenges with our data infrastructure.

Rep: I appreciate you reaching out. Before we dive in, can you tell me a bit about your role at TechVision Analytics and what brought you to look for a solution?

Sarah Chen: Sure. I'm the Director of Data Engineering here at TechVision. We're a mid-size analytics firm with about 150 employees. We work with enterprise clients, processing their data for business intelligence and predictive analytics. The problem is, our current ETL pipeline is becoming a major bottleneck.

Rep: I see. Can you elaborate on what specific challenges you're facing with the ETL process?

Sarah Chen: Well, we're currently processing about 2 terabytes of data daily across multiple client projects. Our legacy system takes anywhere from 8 to 12 hours to complete a full pipeline run. This means we can't provide real-time or even near-real-time insights to our clients. We're also experiencing data quality issues - about 15% of our runs fail due to schema mismatches or connection timeouts.

Rep: Those are significant pain points. How is this impacting your business and your clients?

Sarah Chen: It's affecting us in multiple ways. First, we're losing competitive advantage because competitors are offering real-time dashboards while we're stuck with day-old data. Second, our engineering team spends about 30% of their time just troubleshooting pipeline failures instead of building new features. And third - this is the big one - we've lost two major clients in the past quarter who specifically cited our data latency as the reason for leaving.

Rep: That must be frustrating, especially losing clients over it. When you say 30% of engineering time, how many people are we talking about?

Sarah Chen: We have a team of 12 data engineers. So that's essentially 3.6 full-time employees just doing firefighting instead of value-added work. That's costing us roughly $450,000 annually just in wasted labor, not counting the lost revenue from those clients.

Rep: Those numbers really put it in perspective. Have you looked at other solutions before reaching out to us?

Sarah Chen: Yes, we've evaluated two other platforms. One was too expensive - they wanted $80,000 annually which our CFO rejected. The other seemed promising but their implementation timeline was 6 months, and we need something faster. We can't wait that long.

Rep: I understand the urgency. Our DataFlow platform is specifically designed to address exactly these challenges. We can typically reduce processing time by 85-90%, which would bring your 8-12 hour runs down to under 90 minutes. We also have built-in schema validation and auto-retry logic that reduces failure rates to under 2%.

Sarah Chen: That sounds impressive. What about implementation time?

Rep: Our typical implementation for a company your size is 4-6 weeks, with most clients seeing initial results within the first two weeks. We'd start with one project as a pilot, prove the value, then scale across your other pipelines.

Sarah Chen: That timeline works much better. What about pricing?

Rep: Our pricing is based on data volume and number of pipelines. For your use case - 2TB daily across what I'm assuming is 5-7 major pipelines - we're looking at approximately $45,000 annually. That includes implementation, training, and ongoing support.

Sarah Chen: That's within our budget range. The ROI is clear when you consider we're wasting $450K in engineering time alone. What would the next steps look like?

Rep: I'm glad the value proposition makes sense. Here's what I'd suggest: First, I'd like to schedule a technical deep-dive with your lead data engineer next week. We'll review your current architecture and show exactly how DataFlow would integrate. Second, we can set up a two-week proof of concept with one of your pipelines at no cost, so you can see the results firsthand before making a commitment. How does that sound?

Sarah Chen: That sounds very reasonable. A POC would definitely help me get buy-in from our CTO. Can we target our highest-volume pipeline for the POC? That's where we feel the pain most.

Rep: Absolutely. The high-volume pipeline is actually the perfect test case. It'll give you the most dramatic results. Let me check my calendar... How about I set up that technical call for next Tuesday at 2 PM? I'll bring our solutions architect, Tom, who specializes in analytics firms like yours.

Sarah Chen: Tuesday at 2 works for me. I'll bring our lead engineer, David Martinez. Should I send you any documentation about our current setup beforehand?

Rep: That would be incredibly helpful. If you could send over a high-level architecture diagram and maybe some sample data schemas, that'll let us come prepared with specific recommendations. I'll send you a calendar invite today with a prep questionnaire attached.

Sarah Chen: Perfect. I'll have David pull that together and send it over by Friday.

Rep: Excellent. Sarah, I really appreciate your time today and your transparency about the challenges you're facing. I'm confident we can help you solve these pipeline issues and get you back to focusing on innovation rather than firefighting. Is there anything else you'd like to discuss before we wrap up?

Sarah Chen: No, I think we've covered everything. I'm looking forward to Tuesday's call.

Rep: Great! I'll send that calendar invite within the hour. Have a great rest of your day, Sarah.

Sarah Chen: You too, Mike. Thanks again.

Rep: Thank you. Talk soon!
"
# Processing logic
if process_btn and user_input:
    st.info(user_input)
    st.session_state.processing = True
    
    with st.spinner("🔄 Processing your sales call..."):
        try:
            # Create progress indicators
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Run the agent pipeline
            status_text.text("📊 Analyzing call transcript...")
            progress_bar.progress(25)
            
            runner = InMemoryRunner(agent=postcall_orchestrator)
            
            # Run asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(runner.run_debug(user_input))
            loop.close()
            
            progress_bar.progress(50)
            status_text.text("✅ Analysis complete! Formatting results...")
            
            progress_bar.progress(100)
            status_text.text("✨ All done!")
            
            # Store results
            st.session_state.results = {
                'structured_data': result.get('structured_data', {}),
                'quality_metrics': result.get('quality_metrics', {}),
                'strategic_advice': result.get('strategic_advice', ''),
                'crm_status': result.get('crm_status', ''),
                'sentiment_score': result.get('structured_data', {}).get('sentiment_score', 'N/A'),
                'call_quality': result.get('quality_metrics', {}).get('call_quality_score', 'N/A'),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            st.success("✅ Pipeline executed successfully!")
            progress_bar.empty()
            status_text.empty()
            
        except Exception as e:
            st.error(f"❌ Error processing call: {str(e)}")
            st.exception(e)
        finally:
            st.session_state.processing = False

# Display results
if st.session_state.results:
    st.divider()
    st.header("📊 Analysis Results")
    
    results = st.session_state.results
    structured_data = results.get('structured_data', {})
    quality_metrics = results.get('quality_metrics', {})
    
    # Tab layout for organized results
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Overview", 
        "💡 Insights", 
        "📧 Follow-up Email", 
        "🎯 Recommendations",
        "📈 Quality Report"
    ])
    
    with tab1:
        st.subheader("Call Overview")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Prospect", structured_data.get('prospect_name', 'N/A'))
        with col2:
            st.metric("Company", structured_data.get('company_name', 'N/A'))
        with col3:
            st.metric("Sentiment", f"{structured_data.get('sentiment_score', 'N/A')}/10")
        
        st.subheader("Executive Summary")
        st.write(structured_data.get('summary', 'No summary available'))
        
        st.subheader("CRM Status")
        crm_status = results.get('crm_status', 'No status available')
        if '✅' in crm_status:
            st.success(crm_status)
        else:
            st.warning(crm_status)
    
    with tab2:
        st.subheader("Pain Points Identified")
        pain_points = structured_data.get('pain_points', [])
        if pain_points:
            for i, point in enumerate(pain_points, 1):
                st.markdown(f"**{i}.** {point}")
        else:
            st.info("No specific pain points identified")
        
        st.subheader("Next Steps")
        next_steps = structured_data.get('next_steps', [])
        if next_steps:
            for i, step in enumerate(next_steps, 1):
                st.markdown(f"**{i}.** {step}")
        else:
            st.info("No next steps identified")
    
    with tab3:
        st.subheader("AI-Generated Follow-up Email")
        follow_up = structured_data.get('follow_up_email', 'No email generated')
        
        st.text_area(
            "Email Content:",
            value=follow_up,
            height=400,
            help="Review and customize before sending"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Copy to Clipboard", use_container_width=True):
                st.code(follow_up, language=None)
                st.info("Email content displayed above - use your browser's copy function")
        with col2:
            if st.button("📥 Download as .txt", use_container_width=True):
                st.download_button(
                    "Download Email",
                    data=follow_up,
                    file_name=f"follow_up_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
    
    with tab4:
        st.subheader("Strategic Recommendations")
        advice = results.get('strategic_advice', 'No recommendations available')
        st.markdown(advice)
    
    with tab5:
        st.subheader("Call Quality Assessment")
        
        col1, col2 = st.columns(2)
        with col1:
            quality_score = quality_metrics.get('call_quality_score', 0)
            st.metric("Quality Score", f"{quality_score}/5")
            
            # Visual quality indicator
            quality_labels = {
                5: ("🌟 Exceptional", "success"),
                4: ("✨ Strong", "success"),
                3: ("👍 Satisfactory", "info"),
                2: ("⚠️ Needs Improvement", "warning"),
                1: ("❌ Poor", "error")
            }
            label, msg_type = quality_labels.get(quality_score, ("N/A", "info"))
            
            if msg_type == "success":
                st.success(label)
            elif msg_type == "warning":
                st.warning(label)
            elif msg_type == "error":
                st.error(label)
            else:
                st.info(label)
        
        with col2:
            asked_meeting = quality_metrics.get('asked_for_meeting', False)
            st.metric("Next Meeting Requested", "✅ Yes" if asked_meeting else "❌ No")
        
        st.subheader("Strengths")
        strengths = quality_metrics.get('strengths', [])
        if strengths:
            for strength in strengths:
                st.success(f"✅ {strength}")
        else:
            st.info("No strengths identified")
        
        st.subheader("Areas for Improvement")
        improvements = quality_metrics.get('improvements', [])
        if improvements:
            for improvement in improvements:
                st.warning(f"💡 {improvement}")
        else:
            st.info("No improvements suggested")
    
    # Download full report
    st.divider()
    if st.button("📥 Download Full Report (JSON)", use_container_width=False):
        import json
        report_data = {
            'timestamp': results.get('timestamp'),
            'prospect_info': {
                'name': structured_data.get('prospect_name'),
                'company': structured_data.get('company_name')
            },
            'analysis': structured_data,
            'quality_assessment': quality_metrics,
            'recommendations': results.get('strategic_advice'),
            'crm_status': results.get('crm_status')
        }
        
        st.download_button(
            "Download Report",
            data=json.dumps(report_data, indent=2),
            file_name=f"sales_call_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p>🚀 SalesOps AI Assistant v1.0 | Powered by Google ADK & Gemini</p>
    <p style='font-size: 0.9rem;'>Automate your post-call workflow • Save time • Close more deals</p>
</div>
""", unsafe_allow_html=True)
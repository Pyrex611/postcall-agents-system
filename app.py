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

# Processing logic
if process_btn and user_input:
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
            result = loop.run_until_complete(runner.run({"input": user_input}))
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
# 🚀 SalesOps AI Assistant

An AI-powered post-call automation platform that transcribes, analyzes, and processes sales calls with automated CRM updates and strategic recommendations.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

## 🎯 Features

- **🎙️ Multi-Modal Input**: Support for audio files and text transcripts
- **🧠 AI-Powered Analysis**: Extract key insights using Google's Gemini models
- **📊 Call Quality Scoring**: Automated assessment of sales call performance
- **📧 Auto-Generated Follow-ups**: Personalized email drafts ready for review
- **💾 CRM Automation**: Direct integration with Google Sheets
- **🎯 Strategic Recommendations**: AI-driven next best actions for sales reps
- **📈 Quality Metrics**: Track strengths and improvement areas

## 🏗️ Architecture

```
┌─────────────────┐
│   Streamlit UI  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  PostCall Orchestrator      │
│  (Sequential Agent)         │
└────────┬────────────────────┘
         │
         ├──► 1. Analyst Agent ────► Extract insights
         │
         ├──► 2. Quality Agent ────► Assess call quality
         │
         ├──► 3. CRM Formatter ────► Save to Google Sheets
         │
         └──► 4. Advisor Agent ────► Generate recommendations
```

## 📋 Prerequisites

- Python 3.9 or higher
- Google Cloud Project with Gemini API enabled
- Google Service Account with Google Sheets API access
- Google Sheet for CRM storage

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone git pull origin main --allow-unrelated-histories
cd salesops-ai-assistant
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
GOOGLE_API_KEY=your_gemini_api_key_here
CRM_SHEET_NAME=Sales_CRM_Production
```

### 4. Set Up Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Sheets API
4. Create a Service Account
5. Download the JSON key file
6. Rename it to `service_account.json` and place in project root

### 5. Create Google Sheet

1. Create a new Google Sheet named `Sales_CRM_Production` (or your custom name)
2. Share the sheet with your service account email (found in `service_account.json`)
3. Give "Editor" permissions

### 6. Run the Application

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## 📁 Project Structure

```
salesops-ai-assistant/
│
├── agents/
│   ├── __init__.py
│   ├── analyst_agent_server.py      # Call analysis & insights extraction
│   ├── quality_agent_server.py      # Call quality assessment
│   ├── advisor_agent_server.py      # Strategic recommendations
│   ├── crm_formatter_agent_server.py # CRM data formatting
│   └── postcall_orchestrator.py     # Main orchestration pipeline
│
├── schema/
│   ├── __init__.py
│   └── models.py                     # Pydantic data models
│
├── tools/
│   ├── __init__.py
│   └── google_sheets_crm.py         # Google Sheets integration
│
├── app.py                            # Streamlit UI application
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment template
├── .env                             # Your environment variables (git-ignored)
├── service_account.json             # Google credentials (git-ignored)
└── README.md                        # This file
```

## 💡 Usage

### Text Transcript Analysis

1. Select "Text Transcript" as input type
2. Paste your sales call transcript
3. Click "🚀 Analyze Call"
4. Review results in the organized tabs

### Sample Transcript Format

```
Rep: Hi John, thanks for taking the time today. How are you?

Prospect: Good, thanks for reaching out. I've been looking into solutions for our data pipeline issues.

Rep: Great! Can you tell me more about the challenges you're facing?

Prospect: Well, we're processing about 2TB of data daily, and our current ETL process is taking too long. We need something more efficient.

Rep: I understand. Our platform can handle that volume with 10x faster processing. Would you like to see a demo?

Prospect: Yes, that would be helpful. Can we schedule something for next week?

Rep: Absolutely! How about Tuesday at 2 PM?

Prospect: Perfect, let's do it.
```

## 📊 Output Sections

### 1. **Overview Tab**
- Prospect name and company
- Sentiment score (1-10)
- Executive summary
- CRM update status

### 2. **Insights Tab**
- Identified pain points
- Agreed next steps
- Key discussion topics

### 3. **Follow-up Email Tab**
- AI-generated personalized email
- Copy and download options
- Ready for customization

### 4. **Recommendations Tab**
- 3 prioritized next best actions
- Strategic sales advice
- Deal progression tactics

### 5. **Quality Report Tab**
- Call quality score (1-5)
- Meeting request status
- Strengths identified
- Improvement areas

## 🔧 Configuration

### Customizing Agents

Each agent can be customized by editing their respective files in the `agents/` directory:

- **AnalystAgent**: Modify extraction logic and insights focus
- **QualityAgent**: Adjust scoring criteria
- **AdvisorAgent**: Tailor recommendations style
- **CRMFormatterAgent**: Change CRM field mapping

### Adding Custom Fields to CRM

Edit `tools/google_sheets_crm.py` to add custom columns:

```python
row = [
    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    data.get("prospect_name", ""),
    data.get("company_name", ""),
    # Add your custom fields here
    data.get("custom_field", ""),
]

headers = [
    "Timestamp", "Prospect Name", "Company",
    # Add corresponding headers
    "Custom Field"
]
```

## 🧪 Testing

### Test with Sample Data

```python
# Create a test transcript file
echo "Rep: Hello, this is a test call.
Prospect: Hi, I'm interested in your solution.
Rep: Great! Let me tell you about our features..." > test_transcript.txt
```

Then paste the content in the app and run analysis.

## 🐛 Troubleshooting

### Common Issues

**1. API Key Error**
```
Error: GOOGLE_API_KEY not configured
```
**Solution**: Ensure `.env` file has valid `GOOGLE_API_KEY`

**2. Service Account Error**
```
Error: service_account.json not found
```
**Solution**: Download service account JSON and place in project root

**3. Sheet Not Found**
```
Error: Spreadsheet 'Sales_CRM_Production' not found
```
**Solution**: 
- Create the Google Sheet
- Share with service account email
- Verify `CRM_SHEET_NAME` in `.env`

**4. Permission Denied**
```
Error: The caller does not have permission
```
**Solution**: Share Google Sheet with service account email as Editor

## 🔐 Security Best Practices

1. **Never commit sensitive files**:
   - `.env`
   - `service_account.json`
   
2. **Add to `.gitignore`**:
   ```
   .env
   service_account.json
   *.pyc
   __pycache__/
   ```

3. **Use environment variables** for all credentials

4. **Regularly rotate** API keys and service account keys

## 🚀 Deployment

### Deploy to Streamlit Cloud

1. Push code to GitHub (excluding `.env` and `service_account.json`)
2. Go to [Streamlit Cloud](https://streamlit.io/cloud)
3. Deploy from your repository
4. Add secrets in Streamlit Cloud dashboard:
   - `GOOGLE_API_KEY`
   - Paste `service_account.json` content as `SERVICE_ACCOUNT_JSON`

### Deploy to Other Platforms

- **Heroku**: Use buildpacks for Python and configure env vars
- **AWS**: Deploy on EC2 or ECS with environment configuration
- **Google Cloud Run**: Containerize and deploy with secrets

## 📈 Roadmap

- [ ] Direct integration with Zoom, Google Meet, Loom
- [ ] Real-time audio transcription
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] Integration with popular CRMs (Salesforce, HubSpot)
- [ ] Custom agent training on company data
- [ ] Slack/Teams notifications
- [ ] Mobile app

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

## 💬 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Contact: [your-email@example.com]

## 🙏 Acknowledgments

- Built with [Google AI Development Kit (ADK)](https://github.com/google/adk)
- Powered by [Google Gemini](https://deepmind.google/technologies/gemini/)
- UI with [Streamlit](https://streamlit.io/)

---

**Built with ❤️ for Sales Teams**
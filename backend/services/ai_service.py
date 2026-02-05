"""
AI Analysis Service with multi-provider support
"""
import json
from typing import Dict, Optional
import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from core.config import settings
import logging
# from google.adk.agents import LlmAgent
# from google.adk.models.google_llm import Gemini
# from google.adk.runners import InMemoryRunner

logger = logging.getLogger(__name__)

class AIService:
    """Multi-provider AI analysis service"""
    
    def __init__(self):
        self.anthropic_client = None
        if settings.ANTHROPIC_API_KEY:
            self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        self.openai_client = None
        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        self.google_api_key = settings.GOOGLE_API_KEY
        self.primary_provider = settings.AI_PROVIDER
    
    async def analyze_call(
        self,
        transcript: str,
        provider: Optional[str] = None
    ) -> Dict:
        """
        Analyze sales call transcript
        
        Returns complete analysis with insights, quality metrics, and recommendations
        """
        provider = provider or self.primary_provider
        
        try:
            if provider == "anthropic" and self.anthropic_client:
                return await self._analyze_claude(transcript)
            elif provider == "openai" and self.openai_client:
                return await self._analyze_openai(transcript)
            elif provider == "gemini" and self.google_api_key:
                return await self._analyze_gemini(transcript)
            else:
                raise ValueError(f"Provider {provider} not configured")
        except Exception as e:
            logger.error(f"Analysis failed with {provider}: {e}")
            # Fallback
            if provider != "anthropic" and self.anthropic_client:
                logger.info("Falling back to Claude")
                return await self._analyze_claude(transcript)
            elif provider != "openai" and self.openai_client:
                logger.info("Falling back to OpenAI")
                return await self._analyze_openai(transcript)
            raise
    
    def _get_analysis_prompt(self, transcript: str) -> str:
        """Generate analysis prompt"""
        return f"""Analyze this sales call transcript and extract comprehensive insights.

Transcript:
{transcript}

Provide a detailed analysis in valid JSON format with the following structure:
{{
    "prospect_name": "Full name of the prospect",
    "company_name": "Organization name",
    "summary": "Executive summary (2-3 sentences)",
    "pain_points": ["Pain point 1", "Pain point 2", "Pain point 3"],
    "sentiment_score": 7,
    "next_steps": ["Action 1", "Action 2"],
    "follow_up_email": "Draft follow-up email text (professional, personalized)",
    "quality_metrics": {{
        "quality_score": 4,
        "asked_for_meeting": true,
        "talk_ratio": 40.5,
        "questions_asked": 5,
        "strengths": ["Active listening", "Good discovery"],
        "improvements": ["Could ask more qualifying questions"]
    }},
    "competitors_mentioned": ["Competitor 1", "Competitor 2"],
    "objections": ["Price concern", "Timeline mismatch"],
    "strategic_advice": "### Next Best Actions\\n\\n1. **Action 1**\\n   - Details\\n\\n2. **Action 2**\\n   - Details"
}}

Guidelines:
- sentiment_score: 1-10 (1=very negative, 10=very positive)
- quality_score: 1-5 (1=poor, 5=excellent)
- talk_ratio: Percentage of time rep was talking (ideal: 30-40%)
- Ensure all JSON is valid and properly formatted
- Follow-up email should reference specific points from the call
- Strategic advice should be actionable and specific

Return ONLY the JSON object, no additional text."""

    async def _analyze_claude(self, transcript: str) -> Dict:
        """Analyze using Claude"""
        try:
            message = await self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": self._get_analysis_prompt(transcript)
                }]
            )
            
            response_text = message.content[0].text
            
            # Extract JSON from markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            result = json.loads(response_text.strip())
            return result
            
        except Exception as e:
            logger.error(f"Claude analysis error: {e}")
            raise
    
    async def _analyze_openai(self, transcript: str) -> Dict:
        """Analyze using OpenAI GPT-4"""
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{
                    "role": "system",
                    "content": "You are an expert sales call analyst. Analyze calls and provide structured insights in JSON format."
                }, {
                    "role": "user",
                    "content": self._get_analysis_prompt(transcript)
                }],
                temperature=0.3,
                max_tokens=4096,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"OpenAI analysis error: {e}")
            raise
    
    async def _analyze_gemini(self, transcript: str) -> Dict:
        """Analyze using Google Gemini"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={self.google_api_key}"
                
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": self._get_analysis_prompt(transcript)
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 4096
                    }
                }
                
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                
                # Extract JSON
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                
                return json.loads(text.strip())
                
        except Exception as e:
            logger.error(f"Gemini analysis error: {e}")
            raise


# Singleton
ai_service = AIService()

"""
Production transcription service with multi-provider support
"""
import asyncio
import httpx
from typing import Optional, Dict, List
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Multi-provider transcription service"""
    
    def __init__(self):
        self.deepgram_api_key = settings.DEEPGRAM_API_KEY
        self.assemblyai_api_key = settings.ASSEMBLYAI_API_KEY
        self.openai_api_key = settings.OPENAI_API_KEY
        self.primary_provider = settings.TRANSCRIPTION_PROVIDER
    
    async def transcribe_audio(
        self,
        audio_url: str,
        language: str = "en",
        diarization: bool = True,
        provider: Optional[str] = None
    ) -> Dict:
        """
        Transcribe audio with automatic fallback
        
        Returns:
        {
            "transcript": "Full text",
            "confidence": 95.5,
            "speakers": [...],
            "provider": "deepgram"
        }
        """
        provider = provider or self.primary_provider
        
        try:
            if provider == "deepgram" and self.deepgram_api_key:
                return await self._transcribe_deepgram(audio_url, language, diarization)
            elif provider == "assemblyai" and self.assemblyai_api_key:
                return await self._transcribe_assemblyai(audio_url, language, diarization)
            elif provider == "whisper" and self.openai_api_key:
                return await self._transcribe_whisper(audio_url, language)
            else:
                raise ValueError(f"Provider {provider} not configured")
        except Exception as e:
            logger.error(f"Transcription failed with {provider}: {e}")
            # Fallback to alternative
            if provider != "deepgram" and self.deepgram_api_key:
                logger.info("Falling back to Deepgram")
                return await self._transcribe_deepgram(audio_url, language, diarization)
            raise
    
    async def _transcribe_deepgram(
        self,
        audio_url: str,
        language: str,
        diarization: bool
    ) -> Dict:
        """Deepgram API transcription"""
        async with httpx.AsyncClient(timeout=300.0) as client:
            url = "https://api.deepgram.com/v1/listen"
            params = {
                "language": language,
                "model": "nova-2",
                "smart_format": "true",
                "diarize": str(diarization).lower(),
                "punctuate": "true",
                "utterances": "true"
            }
            headers = {
                "Authorization": f"Token {self.deepgram_api_key}",
                "Content-Type": "application/json"
            }
            payload = {"url": audio_url}
            
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                params=params
            )
            response.raise_for_status()
            result = response.json()
            
            # Parse response
            channel = result["results"]["channels"][0]
            transcript = channel["alternatives"][0]["transcript"]
            confidence = channel["alternatives"][0]["confidence"] * 100
            
            speakers = []
            if diarization and "utterances" in result["results"]:
                for utterance in result["results"]["utterances"]:
                    speakers.append({
                        "speaker": f"Speaker {utterance.get('speaker', 0)}",
                        "text": utterance["transcript"],
                        "start": utterance["start"],
                        "end": utterance["end"],
                        "confidence": utterance.get("confidence", 0)
                    })
            
            return {
                "transcript": transcript,
                "confidence": confidence,
                "speakers": speakers,
                "provider": "deepgram",
                "duration": result["metadata"].get("duration", 0)
            }
    
    async def _transcribe_assemblyai(
        self,
        audio_url: str,
        language: str,
        diarization: bool
    ) -> Dict:
        """AssemblyAI transcription"""
        async with httpx.AsyncClient(timeout=600.0) as client:
            headers = {"authorization": self.assemblyai_api_key}
            
            # Submit job
            payload = {
                "audio_url": audio_url,
                "language_code": language,
                "speaker_labels": diarization
            }
            
            response = await client.post(
                "https://api.assemblyai.com/v2/transcript",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            job_id = response.json()["id"]
            
            # Poll for completion
            max_attempts = 120
            attempt = 0
            
            while attempt < max_attempts:
                response = await client.get(
                    f"https://api.assemblyai.com/v2/transcript/{job_id}",
                    headers=headers
                )
                result = response.json()
                
                if result["status"] == "completed":
                    break
                elif result["status"] == "error":
                    raise Exception(f"AssemblyAI error: {result.get('error')}")
                
                await asyncio.sleep(3)
                attempt += 1
            
            if attempt >= max_attempts:
                raise Exception("AssemblyAI timeout")
            
            # Parse result
            speakers = []
            if diarization and "utterances" in result:
                for utterance in result["utterances"]:
                    speakers.append({
                        "speaker": utterance["speaker"],
                        "text": utterance["text"],
                        "start": utterance["start"] / 1000.0,
                        "end": utterance["end"] / 1000.0,
                        "confidence": utterance.get("confidence", 0)
                    })
            
            return {
                "transcript": result["text"],
                "confidence": result.get("confidence", 0) * 100,
                "speakers": speakers,
                "provider": "assemblyai",
                "duration": result.get("audio_duration", 0)
            }
    
    async def _transcribe_whisper(
        self,
        audio_url: str,
        language: str
    ) -> Dict:
        """OpenAI Whisper transcription"""
        # Download audio first
        async with httpx.AsyncClient(timeout=300.0) as client:
            audio_response = await client.get(audio_url)
            audio_response.raise_for_status()
            audio_data = audio_response.content
        
        # Upload to Whisper
        async with httpx.AsyncClient(timeout=300.0) as client:
            files = {"file": ("audio.mp3", audio_data, "audio/mpeg")}
            data = {
                "model": "whisper-1",
                "language": language,
                "response_format": "verbose_json"
            }
            headers = {"Authorization": f"Bearer {self.openai_api_key}"}
            
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                files=files,
                data=data,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
        
        # Parse segments as speakers
        speakers = []
        if "segments" in result:
            for segment in result["segments"]:
                speakers.append({
                    "speaker": "Speaker 0",
                    "text": segment["text"],
                    "start": segment["start"],
                    "end": segment["end"],
                    "confidence": 0
                })
        
        return {
            "transcript": result["text"],
            "confidence": 0,
            "speakers": speakers,
            "provider": "whisper",
            "duration": result.get("duration", 0)
        }


# Singleton instance
transcription_service = TranscriptionService()

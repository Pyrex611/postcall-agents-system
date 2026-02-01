import whisper
import os

class TranscriptionService:
    def __init__(self, model_size="base"):
        # Loads model into memory once
        self.model = whisper.load_model(model_size)

    def transcribe(self, audio_path):
        """
        Converts audio file to text with speaker timestamps.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Transcribe
        result = self.model.transcribe(audio_path)
        
        # Format segments (Simulating speaker separation logic)
        transcript = ""
        for segment in result["segments"]:
            start = int(segment['start'])
            text = segment['text'].strip()
            transcript += f"[{start}s]: {text}\n"
            
        return transcript
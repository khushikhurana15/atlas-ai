"""
Converts voice messages to text using Groq's Whisper model.
Telegram sends voice notes as .ogg files, which Whisper supports
directly - no audio conversion needed.
"""

from openai import OpenAI
from app.config import GROQ_API_KEY

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    timeout=30.0,
)


def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Takes raw audio bytes (from a Telegram voice message) and returns
    the transcribed text.
    """
    transcription = client.audio.transcriptions.create(
        model="whisper-large-v3",
        file=("voice.ogg", audio_bytes),
    )
    return transcription.text
import ollama
from typing import Optional
from .config import settings

def analyze_transcript(transcript: str) -> Optional[str]:
    """Analyzes transcript using local Ollama instance for viral hooks and captions."""
    system_prompt = (
        "You are a viral content strategist. Analyze the following transcript. "
        "Identify 3 potential 'viral hooks' with timestamps and write a high-engagement caption for each."
    )
    
    try:
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': transcript},
            ]
        )
        return response['message']['content']
    except Exception as e:
        print(f"Ollama analysis failed: {str(e)}")
        return None

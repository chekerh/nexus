import ollama
import json
import re
from typing import Optional, List, Dict
from .config import settings

def analyze_transcript(transcript: str) -> Optional[Dict]:
    """Analyzes transcript using local Ollama instance for viral hooks and captions."""
    system_prompt = (
        "You are an expert viral content strategist. You will receive a transcript where each line starts with a timestamp in the format '[MM:SS.mmm]'. "
        "Your goal is to identify 3 high-impact viral hooks from this content. "
        "For each hook: "
        "1. Identify the EXACT start and end seconds by converting the [MM:SS.mmm] format (e.g., [00:15.500] is 15.5). "
        "2. Write a viral-optimized caption. "
        "3. Provide a catchy hook name. "
        "Return ONLY a raw JSON object (no markdown, no preamble) in this format: "
        '{"hooks": [{"start": float, "end": float, "hook_name": "string", "caption": "string"}]}'
    )

    try:
        # Pre-process transcript to ensure it's not too long for the model context
        # and to highlight the format
        processed_transcript = transcript[:15000] # Cap to avoid context overflow if needed

        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': processed_transcript},
            ]
        )
        content = response['message']['content'].strip()

        # Robust JSON extraction
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(content)
    except Exception as e:
        print(f"Ollama analysis failed: {str(e)}")
        return None

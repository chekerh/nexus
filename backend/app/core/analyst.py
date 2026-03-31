import ollama
import json
import re
from typing import Optional, List, Dict
from .config import settings

def analyze_transcript(transcript: str) -> Optional[Dict]:
    """Analyzes transcript using local Ollama instance for viral hooks and strategy."""
    system_prompt = (
        "You are an expert viral content strategist. You will receive a transcript with timestamps. "
        "Your goal is to identify 3 high-impact viral hooks. "
        "First, provide a 1-2 sentence 'Strategy Insight' about the video's potential. "
        "Then, identify the 3 hooks with exact start/end seconds and captions. "
        "Return your response in this EXACT format: "
        "STRATEGY: <Your insight here>\n"
        "JSON: "
        '{"hooks": [{"start": float, "end": float, "hook_name": "string", "caption": "string"}]}'
    )

    try:
        processed_transcript = transcript[:15000] 

        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': processed_transcript},
            ]
        )
        content = response['message']['content'].strip()

        # Extract Strategy and JSON
        strategy = "Analyzing content structure..."
        if "STRATEGY:" in content:
            strategy_match = re.search(r'STRATEGY:(.*?)(JSON:|$)', content, re.DOTALL)
            if strategy_match:
                strategy = strategy_match.group(1).strip()

        # We'll return the strategy along with the hooks
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            data['strategy_thought'] = strategy
            return data

        return None

    except Exception as e:
        print(f"Ollama analysis failed: {str(e)}")
        return None

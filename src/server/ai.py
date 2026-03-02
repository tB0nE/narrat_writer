import os
import json
import logging
import requests as sync_requests
from typing import Optional
from src.server.utils import load_metadata

logger = logging.getLogger("narrat_api")

def call_llm(prompt: str, retries: int = 3, game_id: str = None) -> str:
    """
    Core LLM API wrapper with retry logic, global/local prompt_prefix support, 
    and detailed logging.
    """
    # Dynamic config
    api_url = os.getenv("API_URL")
    api_model = os.getenv("API_MODEL")
    api_key = os.getenv("API_KEY")
    
    # Prefix Logic
    prefix = os.getenv("GLOBAL_PROMPT_PREFIX", "")
    
    # Per-Game Prefix (overrides global)
    if game_id:
        meta = load_metadata(game_id)
        if meta and meta.prompt_prefix:
            prefix = meta.prompt_prefix
            
    final_prompt = f"{prefix}\n\n{prompt}" if prefix else prompt

    if not api_key or api_key == "YOUR_API_KEY_HERE":
        logger.warning("API Key not configured. Returning fallback data.")
        return '{"title": "Unconfigured Game", "summary": "Please set your API key in .env", "genre": "System", "characters": [], "starting_point": "main", "plot_outline": ""}'

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": api_model, "messages": [{"role": "user", "content": final_prompt}]}
    
    for attempt in range(retries):
        try:
            logger.info(f"AI Request (Attempt {attempt + 1}/{retries}): {final_prompt[:100]}...")
            res = sync_requests.post(api_url, json=payload, headers=headers, timeout=90)
            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"]
            logger.info(f"AI Response received: {len(content)} chars.")
            return content
        except Exception as e:
            logger.error(f"AI Attempt {attempt + 1} failed: {str(e)}")
            if attempt == retries - 1:
                return "" # Return empty on final failure
            import time
            time.sleep(1)
    return ""

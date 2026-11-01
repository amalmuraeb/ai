"""
Phase 2 - Ollama Client
Python interface to the local Ollama API.
"""

import requests
from src.config.ollama import OLLAMA

class OllamaClient:
    def __init__(self):
        self.base_url = OLLAMA["base_url"]
        self.model = OLLAMA["model"]
        self.generate_config = OLLAMA["generate"]

    def generate(
        self,
        prompt,
        model=None,
        response_format=None,
        timeout=None,
    ):
        """Generate text, optionally asking Ollama for structured JSON."""
        url = f"{self.base_url}/api/generate"

        payload = {
            **self.generate_config["payload"],
            "model": model or self.model,
            "prompt": prompt,
        }
        if response_format is not None:
            payload["format"] = response_format
        response = requests.post(
            url,
            json=payload,
            timeout=timeout or self.generate_config["timeout"],
        )
        response.raise_for_status()

        return response.json()["response"]

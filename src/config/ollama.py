"""
Phase 2 - Ollama Configuration
Defines the local model endpoint and generation settings.
"""

OLLAMA = {
    "base_url": "http://127.0.0.1:11434",
    "model": "qwen3:8b",
    "generate": {
        "payload": {
            "stream": False,
            "think": False,
        },
        "timeout": (10, 300),
    },
}

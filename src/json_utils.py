"""
Phase 2 - JSON Utilities
Utility functions for converting model JSON text into Python dictionaries.
"""

import json


def parse_json_response(response: str) -> dict:
    return json.loads(response)

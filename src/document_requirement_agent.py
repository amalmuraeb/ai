"""
Phase 6 - Document Requirement Agent
Uses controlled Ollama fallback for ambiguous document instructions.
"""

import json

from src.config.ollama import OLLAMA
from src.ollama_client import OllamaClient


class DocumentRequirementAgent:
    """Normalize ambiguous posting instructions into supported types."""

    def __init__(self, client=None, model=None):
        self.client = client or OllamaClient()
        self.model = model or OLLAMA["model"]

    def detect(
        self,
        posting_text,
        *,
        supported_document_types,
        ambiguous_instructions,
    ):
        prompt = f"""
You are a document-requirement extraction fallback.

Analyze only materials explicitly required for the initial job application.
Do not include optional materials, materials requested only from finalists,
qualifications, skills, or documents required only after hiring.

You may use only these document_type values:
{json.dumps(list(supported_document_types), indent=2)}

For every requirement, posting_requirement must be an exact contiguous quote
from POSTING TEXT. Do not paraphrase or invent evidence.

Return ONLY this JSON object:
{{
  "analysis_complete": true,
  "requirements": [
    {{
      "document_type": "one supported value",
      "posting_requirement": "exact quote from POSTING TEXT"
    }}
  ],
  "unresolved_requirements": []
}}

Set analysis_complete to false and list unresolved wording when the posting is
still ambiguous. An empty requirements list is valid only when the posting
explicitly states that no application documents are required.

AMBIGUOUS PYTHON RESULTS:
{json.dumps(list(ambiguous_instructions), indent=2)}

POSTING TEXT:
{posting_text}
""".strip()

        response = self.client.generate(prompt, self.model)
        result = json.loads(response)
        if not isinstance(result, dict):
            raise ValueError("Ollama fallback did not return a JSON object.")
        return result

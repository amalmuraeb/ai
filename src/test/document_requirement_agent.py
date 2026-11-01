"""
Phase 6 - Document Requirement Agent Test
Validates the controlled Ollama fallback prompt and JSON contract.
"""

import json

from src.document_requirement_agent import DocumentRequirementAgent


class FakeOllamaClient:
    def __init__(self):
        self.prompt = None
        self.model = None

    def generate(self, prompt, model=None):
        self.prompt = prompt
        self.model = model
        return json.dumps(
            {
                "analysis_complete": True,
                "requirements": [
                    {
                        "document_type": "cv",
                        "posting_requirement": "academic vita",
                    }
                ],
                "unresolved_requirements": [],
            }
        )


def main():
    client = FakeOllamaClient()
    agent = DocumentRequirementAgent(client=client, model="test-model")
    result = agent.detect(
        "Applicants must provide an academic vita.",
        supported_document_types=("cv", "cover_letter"),
        ambiguous_instructions=("academic vita",),
    )

    assert result["analysis_complete"] is True
    assert result["requirements"][0]["document_type"] == "cv"
    assert client.model == "test-model"
    assert "cv" in client.prompt
    assert "exact contiguous quote" in client.prompt
    assert "initial job application" in client.prompt
    assert "academic vita" in client.prompt

    print("Document-requirement agent test passed.")


if __name__ == "__main__":
    main()

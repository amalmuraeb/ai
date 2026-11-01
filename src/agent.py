"""
Phase 2 - Core Infrastructure
Base class for AI agents; builds prompts and calls the Ollama client.
"""

from langgraph.func import task
from src.ollama_client import OllamaClient
from src.config.ollama import OLLAMA
import json


class Agent:
    def __init__(self, name, user_profile, model=None):
        self.name = name
        self.user_profile = user_profile
        self.llm = OllamaClient()
        self.model = model or OLLAMA["model"]

    def run(self, task: str) -> str:
        prompt = self.build_prompt(task)
        return self.llm.generate(prompt, self.model)

    def build_prompt(self, task: str) -> str:
        return f"""
        You are a Job Analysis Agent.

        You must evaluate provisioned job data using this PRIVATE USER PROFILE:

        {json.dumps(self.user_profile, indent=2)}

        TASK:
        Analyze the job and return structured information.

        The job has already passed deterministic Python provisioning.

        Do not evaluate salary, employment type, excluded industries,
        excluded roles, or closing-date thresholds.

        Focus only on technical fit, discipline relevance, skills,
        and meaningful risk assessment.

        LOCATION:
        - Extract or copy the city and state when available.
        - Use null when either value is unavailable.

        Return ONLY valid JSON.

        Use null for missing values.

        {{
            "title": "",
            "company": "",
            "city": null,
            "state": null,
            "posting_date": null,
            "closing_date": null,
            "match_level": "high | medium | low",
            "fit_score": 0,
            "focus_areas": [],
            "must_have_skills": [],
            "missing_skills": [],
            "discipline_match": true,
            "risk_flags": []
        }}

        ANALYSIS RULES:
        - Evaluate the job against the supplied private user profile.
        - Use the profile's target_roles and discipline-focus fields
          when assessing technical and discipline fit.
        - Academic faculty positions are allowed when
          role_scope.academic_faculty_allowed is true.
        - Do not treat an academic or faculty role as a risk solely because it is academic.
        - Identify must-have skills explicitly required by the employer.
        - Identify the role's primary technical, teaching, and research focus
          areas explicitly supported by the posting.
        - Return focus_areas as a concise list of strings. Do not include
          generic duties, employment conditions, or unsupported inferences.
        - Identify meaningful missing skills only when the employer requires them
          and the candidate profile does not support them.
        - Do not infer missing skills solely from the user's interests, preferred fields,
          or target roles.
        - Do not invent missing information.
        - Output only the JSON object, without Markdown or explanatory text.

        PROVISIONED JOB DATA:

        {task}
        """.strip()

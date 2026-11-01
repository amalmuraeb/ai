"""
Phase 5 - Job Analysis Agent
Specialized agent for evaluating job descriptions against the user profile.
"""

from src.agent import Agent


class JobAnalysisAgent(Agent):
    def __init__(self, user_profile):
        super().__init__("Job Analysis Agent", user_profile)

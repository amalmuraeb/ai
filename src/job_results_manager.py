"""
Phase 5 - Job Results Manager
Filters, sorts, and selects structured job-analysis results.
"""
class JobResultsManager:

    def __init__(self, user_profile):
        self.user_profile = user_profile

    def filter_by_recommendation(self, jobs, recommendation):
        return [
            job for job in jobs
            if job.get("final_recommendation") == recommendation
        ]

    def filter_by_min_score(self, jobs, min_score):
        return [
            job for job in jobs
            if job.get("fit_score", 0) >= min_score
        ]

    def sort_by_fit_score(self, jobs, descending=True):
        return sorted(
            jobs,
            key=lambda job: job.get("fit_score", 0),
            reverse=descending
        )

    def get_recommended_jobs(
        self,
        jobs,
        recommendation="apply",
        min_score=None,
    ):
        """
        Return jobs matching the recommendation and
        minimum fit score, sorted by descending fit score.
        """
        if min_score is None:
            min_score = self.user_profile["ranking_constraints"][
                "apply_min_fit_score"
            ]
        filtered = self.filter_by_recommendation(jobs, recommendation)
        filtered = self.filter_by_min_score(filtered, min_score)

        return self.sort_by_fit_score(filtered)

    def get_provisioner_skipped_jobs(self, jobs):
        return [
            job for job in jobs
            if job.get("skipped_before_llm") is True
        ]

    def get_llm_skipped_jobs(self, jobs):
        return [
            job for job in jobs
            if job.get("final_recommendation") == "skip"
            and job.get("skipped_before_llm") is not True
        ]

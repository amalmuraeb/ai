"""
Phase 3 - Job-Board Configuration
Defines HigherEdJobs URLs, selectors, pagination, and request settings.
"""

HIGHEREDJOBS = {
    "base_url": "https://www.higheredjobs.com",
    "request_timeout": 30,
    "max_retries": 3,
    "JOB_POSTS_PER_PAGE": 25,
    "page_stabilization_delay_ms": 3000,
    "navigation_wait_until": "domcontentloaded",
    "job_link_href_prefix": "details.cfm?jobcode=",
    "job_link_selector": "a[href^='details.cfm?JobCode=']",
    "remote_markers": (
        "online/remote",
        "(remote)",
        "fully remote",
        "100% remote",
        "remote position",
        "work remotely",
        "telecommute",
    ),
    "selectors": {
        "title": "#jobtitle-header",
        "company": "#jobLocation .job-inst",
        "location": "#jobLocation .job-loc",
        "job_info": "#jobAttrib",
        "description": "#jobDesc",
    },
    "default_country": "US",
}

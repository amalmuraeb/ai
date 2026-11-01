"""
Phase 4 - Job Provisioner Configuration
Defines the public catalog of reusable filtering rules and heuristics.
"""

MILITARY_CONTEXT = [
    "department of defense",
    "dod",
    "defense contractor",
    "defense systems",
    "military applications",
    "military systems",
    "security clearance",
    "secret clearance",
    "top secret",
    "ts/sci",
    "army",
    "navy",
    "air force",
    "space force",
    "missile systems",
    "weapons systems",
    "combat systems",
    "radar systems",
]

MILITARY_IGNORE_CONTEXT = [
    "protected veteran",
    "veteran status",
    "military spouse",
    "equal opportunity employer",
    "affirmative action",
    "veterans are encouraged to apply",
]

# High-confidence religious markers in an institution's name. Avoid broad
# terms such as "saint" or "st." because they can identify secular schools.
RELIGIOUS_INSTITUTION_NAME_PATTERNS = [
    r"\bsacred\s+heart\b",
    r"\bchristian\b",
    r"\bcatholic\b",
    r"\bbaptist\b",
    r"\bmethodist\b",
    r"\blutheran\b",
    r"\bpresbyterian\b",
    r"\bevangelical\b",
    r"\bjesuit\b",
    r"\bbible\b",
    r"\bbiblical\b",
    r"\btheological\b",
    r"\bseminary\b",
]

# Require mission, values, faith-alignment, or affiliation context. This
# intentionally does not match generic equal-opportunity references to
# religion that appear in many otherwise secular job postings.
RELIGIOUS_MISSION_PATTERNS = [
    r"\bchristian\s+faith\b",
    r"\bchristian\s+values?\b",
    r"\bchristian\s+worldview\b",
    r"\bchristian\s+(?:university|college)\b",
    r"\bfaith\s+alignment\s+with\s+(?:the\s+)?(?:institutional|college|university)\s+mission\b",
    r"\breligious\s+affiliation\s+(?:requirements?|required)\b",
    r"\bstatement\s+of\s+faith\b",
    r"\bfaith[\s-]+based\s+mission\b",
    r"\bintegrat(?:e|ing|ion)\s+faith\s+(?:and|with)\s+learning\b",
]

# Exclude a focus area when its title names the area directly, or when a
# posting description contains a strong cluster of distinct indicators.
# Clustering prevents one incidental course/topic mention from rejecting an
# otherwise relevant ECE, embedded-systems, autonomous-systems, or AI role.
EXCLUDED_FOCUS_AREA_RULES = {
    "Nuclear energy and engineering": {
        "title_patterns": [
            r"\bnuclear\s+energy\b",
            r"\bnuclear\s+engineering\b",
        ],
        "content_patterns": [
            r"\bnuclear\s+energy\b",
            r"\bnuclear\s+engineering\b",
            r"\bnuclear\s+reactors?\b",
            r"\breactor\s+(?:design|engineering|physics)\b",
            r"\bnuclear\s+fuel\b",
            r"\bradiation\s+(?:science|transport|detection)\b",
        ],
        "minimum_content_matches": 2,
    },
    "Power and energy systems": {
        "title_patterns": [
            r"\bpower\s+(?:and\s+)?energy\s+systems?\b",
            r"\bpower\s+systems?\b",
            r"\bpower\s+electronics\b",
            r"\benergy\s+storage\s+systems?\b",
            r"\brenewable\s+energy\b",
            r"\bphotovoltaic\b",
        ],
        "content_patterns": [
            r"\bpower\s+systems?\b",
            r"\bpower\s+electronics\b",
            r"\bphotovoltaic\b",
            r"\bsolar\b",
            r"\bwind\s+power\b",
            r"\brenewable\s+energy\b",
            r"\belectric\s+motors?\b",
            r"\bmotor\s+drives?\b",
            r"\benergy\s+storage\b",
            r"\bbatter(?:y|ies)\b",
            r"\benergy\s+conversion\b",
            r"\bsmart\s+grids?\b",
        ],
        "minimum_content_matches": 2,
    },
    "Deep microelectronics and semiconductor devices": {
        "title_patterns": [
            r"\bmicroelectronics?\b",
            r"\bmicroelectronic\s+engineering\b",
            r"\bsemiconductor(?:s|\s+devices?|\s+research)?\b",
        ],
        "content_patterns": [
            r"\bthin\s+films?\b",
            r"\bsemiconductor\s+devices?\b",
            r"\bCMOS\b",
            r"\bneuromorphic(?:/AI)?\s+devices?\b",
            r"\bmemory\s+technolog(?:y|ies)\b",
            r"\bIII-V\s+epitaxy\b",
            r"\bcleanroom\s+fabrication\b",
            r"\bmicroelectronics?\b",
        ],
        "minimum_content_matches": 2,
    },
    "Medical robotics and biomedical systems": {
        "title_patterns": [
            r"\bmedical\s+robotics?\b",
            r"\bbiomedical(?:\s+engineering|\s+systems?)?\b",
            r"\bneural\s+engineering\b",
        ],
        "content_patterns": [
            r"\bmedical\s+robotics?\b",
            r"\bsurgical\s+robotics?\b",
            r"\brehabilitation\s+robotics?\b",
            r"\belectrophysiology\b",
            r"\belectrical\s+neural\s+recording\b",
            r"\bultrasound\s+imaging\b",
            r"\bneural\s+interfaces?\b",
            r"\bbiomedical\s+(?:interfaces?|systems?)\b",
        ],
        "minimum_content_matches": 2,
    },
    "Mechanical design and fabrication": {
        "title_patterns": [
            r"\bmechanical\s+(?:engineering|design)\b",
            r"\bmechatronics?\b",
            r"\bmanufacturing\s+engineering\b",
        ],
        "content_patterns": [
            r"\bmechanical\s+design\b",
            r"\bmechatronics?\b",
            r"\bphysical\s+fabrication\b",
            r"\bCNC\s+machining\b",
            r"\badditive\s+manufacturing\b",
            r"\bmechanism\s+design\b",
            r"\bactuators?\b",
        ],
        "minimum_content_matches": 3,
    },
    "Cybersecurity": {
        "title_patterns": [
            r"\bcybersecurity\b",
            r"\bcyber\s+security\b",
        ],
        "content_patterns": [
            r"\bcybersecurity\b",
            r"\bcomputer\s+and\s+network\s+security\b",
            r"\bhardware\s+(?:and\s+)?embedded\s+system\s+security\b",
            r"\bprivacy-preserving\s+computing\b",
            r"\bcryptography\b",
        ],
        "minimum_content_matches": 2,
    },
}

EXCLUDED_ROLES_PATTERNS = {
    "Postdoctoral positions": [
        r"\bpost[\s-]?doc(?:toral)?\b",
        r"\bpostdoctoral\b",
        r"\bpost-doctoral\b",
    ],
    "Adjunct teaching roles": [
        r"\badjunct\b",
    ],
    "Chair roles": [
        # Also covers Professor and/& Department Chair titles.
        r"\bchair\b",
    ],
    "Head roles": [
        # Covers Department Head and other academic Head titles.
        r"\bhead\b",
    ],
    "Director roles": [
        # Also covers Professor and/& Director titles.
        r"\bdirector\b",
    ],
    "Research scientist roles": [
        r"\bresearch\s+scientist\b",
    ],
    "Visiting roles": [
        r"\bvisiting\b",
    ],
    "Contract faculty roles": [
        r"\bcontract\s+faculty\b",
    ],
    "One-year lecturer roles": [
        r"\b(?:one|1)[\s-]+year\s+lecturer\b",
    ],
    "Part-time roles": [
        r"\bpart[\s-]?time\b",
        r"\bparttime\b",
    ],
    "Internships": [
        r"\bintern\b",
        r"\binternship\b",
        r"\binternships\b",
    ],
}

SALARY_VALUE_PATTERN = (
    r"\$?\s*(\d{2,3}(?:,\d{3})+|\d{5,6})"
)

DATE_FORMATS = [
    "%Y-%m-%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%m/%d/%Y"
]

# Posting-age boundaries for removing likely stale listings before Phase 4.
POSTING_AGE_REVIEW_YEARS = 1
POSTING_AGE_MAX_YEARS = 2

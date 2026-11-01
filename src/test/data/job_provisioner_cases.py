"""
Phase 4 - Job Provisioner Test Cases
Defines deterministic inputs and expected provisioning outcomes.
"""

TEST_CASES = [
    {
        "name": "valid full-time job above salary threshold",
        "overrides": {},
        "expected": {
            "passed": True,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": None,
            "warning_contains": None,
        },
    },
    {
        "name": "salary range begins below threshold",
        "overrides": {
            "salary": "$90,000 - $140,000",
        },
        "expected": {
            "passed": True,
            "salary_min": 90000,
            "salary_max": 140000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": None,
            "warning_contains": (
                "Salary range begins below the required minimum"
            ),
        },
    },
    {
        "name": "maximum salary below threshold",
        "overrides": {
            "salary": "$70,000 - $95,000",
        },
        "expected": {
            "passed": False,
            "salary_min": 70000,
            "salary_max": 95000,
            "salary_match": False,
            "employment_type_match": True,
            "reason_contains": "Maximum salary",
            "warning_contains": None,
        },
    },
    {
        "name": "postdoctoral role is excluded",
        "overrides": {
            "title": "Postdoctoral Associate",
            "raw_text": (
                "Postdoctoral Associate in Electrical Engineering. "
                "This is a full-time research appointment."
            ),
        },
        "expected": {
            "passed": False,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": "Excluded role",
            "warning_contains": None,
        },
    },
    {
        "name": "adjunct role is excluded",
        "overrides": {
            "title": "Adjunct Lecturer in Computer Engineering",
            "raw_text": (
                "Adjunct Lecturer in Computer Engineering. "
                "The successful candidate will teach embedded systems."
            ),
        },
        "expected": {
            "passed": False,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": "Excluded role",
            "warning_contains": None,
        },
    },
    {
        "name": "part-time role is excluded by title",
        "overrides": {
            "title": "Part-Time Lecturer in Electrical Engineering",
            "employment_type": "full-time",
            "raw_text": (
                "Part-Time Lecturer in Electrical Engineering. "
                "The successful candidate will teach undergraduate courses."
            ),
        },
        "expected": {
            "passed": False,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": "Excluded role: Part-time roles",
            "warning_contains": None,
        },
    },
    {
        "name": "internship role is excluded by title",
        "overrides": {
            "title": "Electrical Engineering Intern",
            "employment_type": "full-time",
            "raw_text": (
                "Electrical Engineering Intern supporting embedded "
                "systems development."
            ),
        },
        "expected": {
            "passed": False,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": "Excluded role: Internships",
            "warning_contains": None,
        },
    },
    {
        "name": "military defense role is excluded",
        "overrides": {
            "raw_text": (
                "Senior Electrical Engineer supporting Department "
                "of Defense radar systems. Security clearance required."
            ),
        },
        "expected": {
            "passed": False,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": "Excluded industry: Military/Defense",
            "warning_contains": None,
        },
    },
    {
        "name": "veteran status wording is not military work",
        "overrides": {
            "raw_text": (
                "Assistant Professor of Electrical Engineering. "
                "The university is an equal opportunity employer "
                "and does not discriminate based on veteran status."
            ),
        },
        "expected": {
            "passed": True,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": None,
            "warning_contains": None,
        },
    },
    {
        "name": "closing date inside configured threshold",
        "overrides": {
            "closing_date_offset_days": 30,
        },
        "expected": {
            "passed": False,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": "Closing date is less than",
            "warning_contains": None,
        },
    },
    {
        "name": "missing salary remains eligible for LLM review",
        "overrides": {
            "salary": None,
        },
        "expected": {
            "passed": True,
            "salary_min": None,
            "salary_max": None,
            "salary_match": None,
            "employment_type_match": True,
            "reason_contains": None,
            "warning_contains": None,
        },
    },
    {
        "name": "missing employment type is rejected",
        "overrides": {
            "employment_type": None,
        },
        "expected": {
            "passed": False,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": False,
            "reason_contains": "Employment type is not allowed",
            "warning_contains": None,
        },
    },
]


# Title-only exclusions must be deterministic so these jobs never consume
# an Ollama request or depend on LLM inference about employment semantics.
TITLE_EXCLUSION_CASES = [
    (
        "professor and department chair",
        "Professor and Department Chair of Electrical Engineering",
        "Chair roles",
    ),
    (
        "professor ampersand department chair",
        "Professor & Department Chair of Computer Engineering",
        "Chair roles",
    ),
    (
        "professor and director",
        "Professor & Director of Embedded Systems",
        "Director roles",
    ),
    (
        "chair",
        "Department Chair, Electrical Engineering",
        "Chair roles",
    ),
    (
        "department head",
        "Professor and Department Head of Electrical Engineering",
        "Head roles",
    ),
    (
        "head",
        "Head of Computer Engineering",
        "Head roles",
    ),
    (
        "director",
        "Director of Computer Engineering",
        "Director roles",
    ),
    (
        "research scientist",
        "Research Scientist in Autonomous Systems",
        "Research scientist roles",
    ),
    (
        "visiting",
        "Visiting Assistant Professor of Electrical Engineering",
        "Visiting roles",
    ),
    (
        "contract faculty",
        "Contract Faculty in Computer Engineering",
        "Contract faculty roles",
    ),
    (
        "one-year lecturer",
        "One-Year Lecturer in Electrical Engineering",
        "One-year lecturer roles",
    ),
    (
        "numeric one-year lecturer",
        "1-Year Lecturer in Computer Engineering",
        "One-year lecturer roles",
    ),
]


TEST_CASES.extend(
    {
        "name": f"{name} title is excluded",
        "overrides": {
            "title": title,
            "employment_type": "full-time",
        },
        "expected": {
            "passed": False,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": f"Excluded role: {category}",
            "warning_contains": None,
        },
    }
    for name, title, category in TITLE_EXCLUSION_CASES
)


RELIGIOUS_INSTITUTION_CASES = [
    (
        "Sacred Heart institution name",
        {
            "company": "Sacred Heart University",
        },
        False,
    ),
    (
        "religious institution name",
        {
            "company": "Texas Christian University",
        },
        False,
    ),
    (
        "Christian faith mission language",
        {
            "raw_text": (
                "Candidates must demonstrate Christian faith alignment "
                "with institutional mission."
            ),
        },
        False,
    ),
    (
        "Christian values mission language",
        {
            "raw_text": (
                "Academic role with emphasis on Christian values."
            ),
        },
        False,
    ),
    (
        "Christian university mission language",
        {
            "raw_text": (
                "Commitment to quality teaching in a Christian university."
            ),
        },
        False,
    ),
    (
        "generic equal opportunity religion wording",
        {
            "raw_text": (
                "The university provides equal opportunity without regard "
                "to race, sex, religion, national origin, or veteran status."
            ),
        },
        True,
    ),
]


TEST_CASES.extend(
    {
        "name": name,
        "overrides": overrides,
        "expected": {
            "passed": should_pass,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": (
                None
                if should_pass
                else "Excluded institution: Religious mission or affiliation"
            ),
            "warning_contains": None,
        },
    }
    for name, overrides, should_pass in RELIGIOUS_INSTITUTION_CASES
)


EXCLUDED_FOCUS_AREA_CASES = [
    (
        "nuclear energy title",
        {"title": "Assistant Professor of Nuclear Energy"},
        "Nuclear energy and engineering",
    ),
    (
        "nuclear engineering title",
        {"title": "Assistant Professor of Nuclear Engineering"},
        "Nuclear energy and engineering",
    ),
    (
        "nuclear engineering description cluster",
        {
            "raw_text": (
                "Research expertise is required in nuclear reactors, "
                "reactor physics, nuclear fuel, and radiation transport."
            ),
        },
        "Nuclear energy and engineering",
    ),
    (
        "power systems title",
        {"title": "Assistant Professor - Power Systems"},
        "Power and energy systems",
    ),
    (
        "energy storage title",
        {"title": "Assistant Professor in Energy Storage Systems"},
        "Power and energy systems",
    ),
    (
        "power and renewable description cluster",
        {
            "raw_text": (
                "Research focuses on power electronics, photovoltaic "
                "systems, wind power, and renewable energy systems."
            ),
        },
        "Power and energy systems",
    ),
    (
        "microelectronics title",
        {"title": "Assistant Professor of Microelectronic Engineering"},
        "Deep microelectronics and semiconductor devices",
    ),
    (
        "semiconductor description cluster",
        {
            "raw_text": (
                "Required research includes thin films, semiconductor "
                "devices, CMOS, memory technologies, and III-V epitaxy."
            ),
        },
        "Deep microelectronics and semiconductor devices",
    ),
    (
        "medical robotics description cluster",
        {
            "raw_text": (
                "The program emphasizes medical robotics, surgical "
                "robotics, rehabilitation robotics, and neural interfaces."
            ),
        },
        "Medical robotics and biomedical systems",
    ),
    (
        "biomedical systems title",
        {"title": "Assistant Professor of Biomedical Systems"},
        "Medical robotics and biomedical systems",
    ),
    (
        "mechanical design description cluster",
        {
            "raw_text": (
                "Expertise is required in mechanical design, mechatronics, "
                "CNC machining, additive manufacturing, mechanism design, "
                "and actuators."
            ),
        },
        "Mechanical design and fabrication",
    ),
    (
        "mechanical engineering title",
        {"title": "Assistant Professor of Mechanical Engineering"},
        "Mechanical design and fabrication",
    ),
    (
        "cybersecurity title",
        {"title": "Assistant Professor of Cybersecurity"},
        "Cybersecurity",
    ),
    (
        "cybersecurity description cluster",
        {
            "raw_text": (
                "Research expertise in cybersecurity, computer and network "
                "security, cryptography, and privacy-preserving computing."
            ),
        },
        "Cybersecurity",
    ),
]


TEST_CASES.extend(
    {
        "name": f"{name} is excluded",
        "overrides": overrides,
        "expected": {
            "passed": False,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": f"Excluded focus area: {focus_area}",
            "warning_contains": None,
        },
    }
    for name, overrides, focus_area in EXCLUDED_FOCUS_AREA_CASES
)


TEST_CASES.append(
    {
        "name": "single incidental power topic remains eligible",
        "overrides": {
            "title": "Assistant Professor of Computer Engineering",
            "raw_text": (
                "The candidate will teach embedded systems, AI, digital "
                "signal processing, and one course in power systems."
            ),
        },
        "expected": {
            "passed": True,
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_match": True,
            "employment_type_match": True,
            "reason_contains": None,
            "warning_contains": None,
        },
    }
)

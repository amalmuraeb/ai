"""
Phase 6 - Document Manager
Inventories source materials and builds application-readiness plans.
"""

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from src.config.documents import ORIGINAL_DOCUMENTS_DIR
from src.version import __version__


DOCUMENT_TYPES = {
    "cv": {
        "category": "cv",
        "aliases": ("cv", "curriculum vitae"),
        "posting_patterns": (r"\bcurriculum\s+vitae\b", r"\bCV\b"),
    },
    "cover_letter": {
        "category": "dynamic",
        "aliases": ("cover letter", "cover_letter"),
        "posting_patterns": (r"\bcover\s+letter\b",),
    },
    "personal_statement": {
        "category": "dynamic",
        "aliases": ("personal statement", "personal_statement"),
        "posting_patterns": (r"\bpersonal\s+statement\b",),
    },
    "research_statement": {
        "category": "dynamic",
        "aliases": (
            "research statement",
            "research_statement",
            "research plan",
        ),
        "posting_patterns": (r"\bresearch\s+(?:statement|plan)\b",),
    },
    "teaching_statement": {
        "category": "dynamic",
        "aliases": (
            "teaching statement",
            "teaching_statement",
            "teaching philosophy",
        ),
        "posting_patterns": (
            r"\bteaching\s+(?:philosophy\s+)?statement\b",
            r"\bstatement\s+of\s+teaching\s+philosophy\b",
        ),
    },
    "service_statement": {
        "category": "dynamic",
        "aliases": ("service statement", "service_statement"),
        "posting_patterns": (r"\bservice\s+statement\b",),
    },
    "references": {
        "category": "static",
        "aliases": ("references", "reference list"),
        "posting_patterns": (
            r"\b(?:professional\s+)?references?\b",
            r"\breference\s+(?:list|letters?)\b",
        ),
    },
    "transcripts": {
        "category": "static",
        "aliases": ("transcript", "transcripts"),
        "posting_patterns": (r"\b(?:official|unofficial)?\s*transcripts?\b",),
    },
    "representative_publications": {
        "category": "static",
        "aliases": (
            "representative publications",
            "writing samples",
            "published papers",
        ),
        "posting_patterns": (
            r"\brepresentative\s+publications?\b",
            r"\bwriting\s+samples?\b",
            r"\bpublished\s+(?:journal\s+)?papers?\b",
        ),
    },
}

APPLICATION_SECTION_START_PATTERNS = (
    r"applicants?\s+(?:are|is)\s+required\s+to\s+.*following",
    r"applicants?\s+(?:should|must)\s+submit\b",
    r"required\s+application\s+materials",
    r"application\s+materials\s+(?:include|must\s+include)",
)

APPLICATION_SECTION_END_PATTERNS = (
    r"^submission\s+of\s+materials\b",
    r"^https?://",
    r"^additional\s+materials\b",
    r"^full\s+consideration\b",
    r"^job\s+contact\b",
    r"^(?:salary|benefits|qualifications|minimum\s+qualifications)\s*:",
)


class DocumentManager:
    """Build a Phase 6 document plan for an analyzed apply job."""

    CATEGORIES = ("cv", "static", "dynamic")

    def __init__(
        self,
        docs_root=ORIGINAL_DOCUMENTS_DIR,
        requirement_agent=None,
    ):
        self.docs_root = Path(docs_root)
        self.requirement_agent = requirement_agent

    def inventory(self):
        """Return a stable inventory for every supported document folder."""
        documents = {category: [] for category in self.CATEGORIES}

        for category in self.CATEGORIES:
            category_path = self.docs_root / category

            if not category_path.is_dir():
                continue

            paths = (
                sorted(category_path.rglob("*"))
                if category == "dynamic"
                else sorted(category_path.iterdir())
            )
            for file_path in paths:
                # WSL can expose Windows download metadata as a sibling such
                # as ``resume.docx:Zone.Identifier``. Word can likewise leave
                # ``~$`` lock files. Neither is an application document, and
                # their names can otherwise win alias-based template matching.
                if self._is_ignored_inventory_file(file_path):
                    continue
                if file_path.is_file():
                    documents[category].append(
                        {
                            "name": file_path.name,
                            "path": str(file_path),
                            "extension": file_path.suffix.lower(),
                        }
                    )
                elif category != "dynamic" and file_path.is_dir() and any(
                    child.is_file() for child in file_path.rglob("*")
                ):
                    # A named directory can represent one required static
                    # bundle, such as representative_publications/. Its
                    # contents stay private; Phase 6 records only the bundle.
                    documents[category].append(
                        {
                            "name": file_path.name,
                            "path": str(file_path),
                            "extension": "",
                        }
                    )

        return documents

    @staticmethod
    def _is_ignored_inventory_file(file_path):
        """Exclude Windows metadata and Office lock files from inventory."""
        name = file_path.name
        return name.startswith("~$") or ":Zone.Identifier" in name

    def summary(self):
        return {
            category: len(files)
            for category, files in self.inventory().items()
        }

    def has_document(self, keyword):
        keyword = self._normalize_text(keyword)

        return any(
            keyword in self._normalize_text(file["name"])
            for files in self.inventory().values()
            for file in files
        )

    def check_requirements(self, required_docs):
        """Retain the original availability API for simple callers."""
        available = []
        missing = []

        for document_name in required_docs:
            target = available if self.has_document(document_name) else missing
            target.append(document_name)

        return {"available": available, "missing": missing}

    def select_template(self, document_type, inventory=None):
        """Return the first matching template for a canonical document type."""
        specification = DOCUMENT_TYPES.get(document_type)
        if specification is None:
            raise ValueError(f"Unsupported document type: {document_type}")

        if inventory is None:
            inventory = self.inventory()

        candidates = inventory[specification["category"]]
        for candidate in candidates:
            normalized_name = self._normalize_text(
                Path(candidate["name"]).stem
            )
            if any(
                self._normalize_text(alias) in normalized_name
                for alias in specification["aliases"]
            ):
                return candidate

        return None

    def detect_required_documents(self, posting_text):
        """Extract explicit application materials from a posting body.

        The detector is intentionally deterministic. It preserves each source
        instruction as evidence and flags unrecognized required items for
        manual review instead of silently dropping or guessing them.
        """
        lines = [line.strip() for line in str(posting_text or "").splitlines()]
        start_index = next(
            (
                index
                for index, line in enumerate(lines)
                if any(
                    re.search(pattern, line, flags=re.IGNORECASE)
                    for pattern in APPLICATION_SECTION_START_PATTERNS
                )
            ),
            None,
        )

        if start_index is None:
            detection = {
                "requirements": [],
                "unclassified_requirements": [],
                "manual_review_required": True,
                "review_reason": (
                    "No explicit required-application-materials section "
                    "was detected."
                ),
            }
            return self._apply_ollama_fallback(posting_text, detection)

        requirements = []
        unclassified = []
        seen_types = set()

        for line_index, source_line in enumerate(lines[start_index:]):
            if not source_line:
                continue
            if line_index > 0 and any(
                re.search(pattern, source_line, flags=re.IGNORECASE)
                for pattern in APPLICATION_SECTION_END_PATTERNS
            ):
                break

            instruction = re.sub(
                r"^(?:[*•-]|\d+[.)])\s*",
                "",
                source_line,
            ).strip()
            document_types = self._classify_posting_requirements(instruction)

            # A heading-only start line is expected and is not an unknown
            # required material. Later unmatched lines remain auditable.
            if not document_types and line_index > 0:
                unclassified.append(instruction)
            else:
                for document_type in document_types:
                    if document_type not in seen_types:
                        requirements.append(
                            {
                                "document_type": document_type,
                                "posting_requirement": instruction,
                            }
                        )
                        seen_types.add(document_type)

        detection = {
            "requirements": requirements,
            "unclassified_requirements": unclassified,
            "manual_review_required": bool(unclassified),
            "review_reason": (
                "One or more required materials could not be classified."
                if unclassified
                else None
            ),
        }
        return self._apply_ollama_fallback(posting_text, detection)

    def build_application_plan(self, job, posting_text):
        """Detect and resolve required documents for one analyzed apply job."""
        self._validate_apply_job(job)
        inventory = self.inventory()
        detection = self.detect_required_documents(posting_text)
        requirements = []

        for detected in detection["requirements"]:
            document_type = detected["document_type"]
            selected_template = self.select_template(
                document_type,
                inventory=inventory,
            )
            requirements.append(
                {
                    "document_type": document_type,
                    "posting_requirement": detected["posting_requirement"],
                    "available": selected_template is not None,
                    "selected_template": selected_template,
                }
            )

        missing = [
            requirement["document_type"]
            for requirement in requirements
            if not requirement["available"]
        ]

        return {
            "job": self._job_identity(job),
            "required_documents": requirements,
            "unclassified_requirements": detection[
                "unclassified_requirements"
            ],
            "missing_documents": missing,
            "manual_review_required": detection["manual_review_required"],
            "review_reason": detection["review_reason"],
            "ollama_fallback_used": detection["ollama_fallback_used"],
            "ollama_fallback_error": detection["ollama_fallback_error"],
            "ready": not missing and not detection["manual_review_required"],
        }

    def build_application_plans(self, posting_results):
        """Build one Phase 6 plan for every retrieved apply posting."""
        plans = []

        for posting_result in posting_results:
            job = posting_result["job"]
            retrieval_error = posting_result.get("retrieval_error")

            if retrieval_error:
                self._validate_apply_job(job)
                plans.append(
                    {
                        "job": self._job_identity(job),
                        "required_documents": [],
                        "unclassified_requirements": [],
                        "missing_documents": [],
                        "manual_review_required": True,
                        "review_reason": (
                            "Unable to retrieve or parse the Phase 6 "
                            f"posting: {retrieval_error}"
                        ),
                        "ollama_fallback_used": False,
                        "ollama_fallback_error": None,
                        "ready": False,
                    }
                )
                continue

            plans.append(
                self.build_application_plan(
                    job,
                    posting_result.get("posting_text"),
                )
            )

        return plans

    def load_apply_jobs(self, report_path):
        """Load and validate jobs from an apply-report JSON file."""
        report_path = Path(report_path)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        jobs = report.get("jobs")

        if not isinstance(jobs, list):
            raise ValueError("Apply report must contain a 'jobs' list.")

        for job in jobs:
            self._validate_apply_job(job)

        return jobs

    def create_document_manager_report(
        self,
        application_plans,
        *,
        apply_jobs=None,
        job_board="higheredjobs",
        run_started_at=None,
        pipeline_name="Job-Agent Live Run",
    ):
        """Create the persistent Phase 6 batch-report structure."""
        plans = deepcopy(list(application_plans))
        for sequence_number, plan in enumerate(plans, start=1):
            job = plan["job"]
            # Keep user-maintained application tracking beside the job's
            # identity fields while giving every report row a stable label.
            assigned_sequence = job.pop(
                "job_sequence_number",
                None,
            ) or sequence_number
            applied = job.pop("applied?", "No")
            application_date = job.pop("application_date", None)
            plan["job"] = {
                "job_sequence_number": assigned_sequence,
                "title": job.pop("title"),
                "applied?": applied,
                "application_date": application_date,
                **job,
            }
        validation = self.validate_application_plans(
            plans,
            apply_jobs if apply_jobs is not None else plans,
        )
        started_at = run_started_at or datetime.now().astimezone()
        created_at = datetime.now().astimezone()

        return {
            "report_metadata": {
                "report_name": "document_manager.json",
                "report_version": "1.1",
                "software_version": __version__,
                "pipeline": pipeline_name,
                "phase": "Phase 6 — Document Manager",
                "job_board": job_board,
                "run_started_at": started_at.isoformat(
                    timespec="seconds"
                ),
                "report_created_at": created_at.isoformat(
                    timespec="seconds"
                ),
                "last_job_sequence_number": max(
                    (
                        plan["job"]["job_sequence_number"]
                        for plan in plans
                    ),
                    default=0,
                ),
            },
            "job_count": len(plans),
            "ready_count": sum(bool(plan.get("ready")) for plan in plans),
            "missing_documents_count": sum(
                bool(plan.get("missing_documents")) for plan in plans
            ),
            "manual_review_count": sum(
                bool(plan.get("manual_review_required"))
                for plan in plans
            ),
            "jobs": plans,
            "validation": validation,
        }

    def validate_application_plans(self, plans, apply_jobs):
        """Reconcile Phase 6 plans one-to-one with Phase 5 apply jobs."""
        plans = list(plans)
        apply_jobs = list(apply_jobs)
        expected_urls = [
            self._source_url(job)
            for job in apply_jobs
        ]
        actual_urls = [
            self._source_url(plan)
            for plan in plans
        ]

        return {
            "all_apply_jobs_accounted_for": (
                len(plans) == len(apply_jobs)
                and set(actual_urls) == set(expected_urls)
            ),
            "unique_apply_source_urls": (
                None not in expected_urls
                and len(expected_urls) == len(set(expected_urls))
            ),
            "unique_plan_source_urls": (
                None not in actual_urls
                and len(actual_urls) == len(set(actual_urls))
            ),
        }

    def save_document_manager_report(
        self,
        application_plans,
        output_file,
        **report_options,
    ):
        """Create and write ``document_manager.json``."""
        report = self.create_document_manager_report(
            application_plans,
            **report_options,
        )
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return report

    def find_job(self, jobs, *, title, company, city=None, state=None):
        """Select one job using stable identity fields from the report."""
        expected = {
            "title": title,
            "company": company,
            "city": city,
            "state": state,
        }
        matches = [
            job
            for job in jobs
            if all(
                value is None or job.get(field) == value
                for field, value in expected.items()
            )
        ]

        if not matches:
            raise LookupError("No matching apply job was found.")
        if len(matches) > 1:
            raise LookupError("Multiple matching apply jobs were found.")

        return matches[0]

    def report(self):
        return {
            "inventory": self.inventory(),
            "summary": self.summary(),
        }

    @staticmethod
    def _normalize_text(value):
        return " ".join(
            str(value).lower().replace("_", " ").replace("-", " ").split()
        )

    @staticmethod
    def _classify_posting_requirements(instruction):
        matches = []

        for document_type, specification in DOCUMENT_TYPES.items():
            for pattern in specification["posting_patterns"]:
                match = re.search(pattern, instruction, flags=re.IGNORECASE)
                if match:
                    matches.append((match.start(), document_type))
                    break

        matches.sort()
        return [document_type for _, document_type in matches]

    @staticmethod
    def _resolve_posting_quote(posting_text, evidence):
        """Map an LLM quote back to the posting despite formatting changes.

        HTML-to-text extraction can replace line breaks and punctuation around
        otherwise exact wording. Match the same contiguous word sequence, then
        retain the posting's original text as the auditable report evidence.
        """
        posting_text = str(posting_text)
        evidence = str(evidence)
        if evidence in posting_text:
            return evidence

        token_pattern = re.compile(r"\w+(?:['’]\w+)*", re.UNICODE)
        posting_tokens = list(token_pattern.finditer(posting_text))
        evidence_tokens = [
            match.group(0).casefold()
            for match in token_pattern.finditer(evidence)
        ]
        if not evidence_tokens:
            return None

        posting_values = [
            match.group(0).casefold()
            for match in posting_tokens
        ]
        match_length = len(evidence_tokens)
        for start in range(len(posting_values) - match_length + 1):
            if posting_values[start:start + match_length] == evidence_tokens:
                return posting_text[
                    posting_tokens[start].start():
                    posting_tokens[start + match_length - 1].end()
                ]

        return None

    def _apply_ollama_fallback(self, posting_text, detection):
        """Resolve ambiguity only through validated, evidence-backed output."""
        detection = {
            **detection,
            "ollama_fallback_used": False,
            "ollama_fallback_error": None,
        }

        if (
            not detection["manual_review_required"]
            or self.requirement_agent is None
        ):
            return detection

        detection["ollama_fallback_used"] = True

        try:
            fallback = self.requirement_agent.detect(
                posting_text,
                supported_document_types=tuple(DOCUMENT_TYPES),
                ambiguous_instructions=detection[
                    "unclassified_requirements"
                ],
            )
            requirements = fallback.get("requirements")
            unresolved = fallback.get("unresolved_requirements")
            analysis_complete = fallback.get("analysis_complete")

            if not isinstance(requirements, list):
                raise ValueError("Fallback requirements must be a list.")
            if not isinstance(unresolved, list):
                raise ValueError(
                    "Fallback unresolved_requirements must be a list."
                )
            if not isinstance(analysis_complete, bool):
                raise ValueError("Fallback analysis_complete must be boolean.")

            existing_types = {
                item["document_type"]
                for item in detection["requirements"]
            }
            validated_requirements = []
            validation_errors = []

            for requirement in requirements:
                if not isinstance(requirement, dict):
                    validation_errors.append(
                        "Each fallback requirement must be an object."
                    )
                    continue
                document_type = requirement.get("document_type")
                evidence = requirement.get("posting_requirement")

                if document_type not in DOCUMENT_TYPES:
                    validation_errors.append(
                        f"Unsupported fallback document type: {document_type}"
                    )
                    continue
                if not isinstance(evidence, str) or not evidence.strip():
                    validation_errors.append(
                        "Fallback evidence must be non-empty."
                    )
                    continue

                posting_quote = self._resolve_posting_quote(
                    posting_text,
                    evidence,
                )
                if posting_quote is None:
                    validation_errors.append(
                        "Fallback evidence is not an exact posting quote."
                    )
                    continue
                if document_type not in existing_types:
                    validated_requirements.append(
                        {
                            "document_type": document_type,
                            "posting_requirement": posting_quote,
                        }
                    )
                    existing_types.add(document_type)

            unresolved = [*unresolved, *validation_errors]
            if analysis_complete and not unresolved and not (
                detection["requirements"] or validated_requirements
            ):
                raise ValueError(
                    "A complete fallback returned no document requirements."
                )

            detection["requirements"].extend(validated_requirements)
            detection["unclassified_requirements"] = unresolved
            detection["manual_review_required"] = (
                not analysis_complete or bool(unresolved)
            )
            detection["review_reason"] = (
                None
                if not detection["manual_review_required"]
                else "Ollama could not fully resolve application materials."
            )
            if validation_errors:
                detection["ollama_fallback_error"] = "; ".join(
                    validation_errors
                )
        except Exception as error:
            detection["manual_review_required"] = True
            detection["review_reason"] = (
                "Ollama fallback failed validation; manual review required."
            )
            detection["ollama_fallback_error"] = (
                f"{type(error).__name__}: {error}"
            )

        return detection

    @staticmethod
    def _job_identity(job):
        identity = {
            "title": job["title"],
            "company": job["company"],
            "city": job.get("city"),
            "state": job.get("state"),
            "remote?": job.get("remote?", "No"),
            "closing_date": job.get("closing_date"),
            "source_url": job.get("source_url"),
        }
        if job.get("job_sequence_number") is not None:
            identity = {
                "job_sequence_number": job["job_sequence_number"],
                **identity,
            }
        return identity

    @staticmethod
    def _source_url(item):
        if "job" in item and isinstance(item["job"], dict):
            return item["job"].get("source_url")
        return item.get("source_url")

    @staticmethod
    def _validate_apply_job(job):
        if not isinstance(job, dict):
            raise ValueError("Each apply job must be a JSON object.")

        missing_fields = [
            field
            for field in ("title", "company")
            if not job.get(field)
        ]
        if missing_fields:
            raise ValueError(
                "Apply job is missing required field(s): "
                + ", ".join(missing_fields)
            )

        if job.get("final_recommendation") != "apply":
            raise ValueError(
                "Phase 6 accepts only jobs with an 'apply' recommendation."
            )

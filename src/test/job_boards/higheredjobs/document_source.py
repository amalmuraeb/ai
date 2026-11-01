"""
Phase 6 - HigherEdJobs Document Source Test
Validates posting retrieval isolation and browser cleanup.
"""

from src.job_boards.higheredjobs.document_source import (
    HigherEdJobsDocumentSource,
)


class FakeClient:
    def __init__(self):
        self.closed = False

    def connect_browser(self):
        return None

    def get_job_page(self, source_url):
        if source_url.endswith("failure"):
            raise RuntimeError("Simulated retrieval failure.")
        return "posting html"

    def close(self):
        self.closed = True


class FakeReader:
    def from_html(self, html, source_url=None):
        return {"raw_text": "Application Instructions"}


def main():
    jobs = [
        {
            "title": "Successful job",
            "company": "University A",
            "source_url": "https://example.test/success",
        },
        {
            "title": "Failed job",
            "company": "University B",
            "source_url": "https://example.test/failure",
        },
    ]
    client = FakeClient()
    source = HigherEdJobsDocumentSource(
        client=client,
        reader=FakeReader(),
    )

    results = source.load_postings(jobs)
    assert len(results) == 2
    assert results[0]["posting_text"] == "Application Instructions"
    assert results[0]["retrieval_error"] is None
    assert results[1]["posting_text"] is None
    assert "Simulated retrieval failure" in results[1]["retrieval_error"]
    assert client.closed is True

    print("HigherEdJobs document-source test passed.")


if __name__ == "__main__":
    main()

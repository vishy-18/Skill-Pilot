from navigator.services import NavigatorService


class FakePortal:
    def __init__(self, *args, **kwargs):
        pass

    async def find_matching_jobs(self, role, skills):
        return [{"job_id": "job-1", "title": "Backend Intern"}]

    async def fetch_job(self, job_id):
        return {
            "job_id": job_id,
            "title": "Backend Intern",
            "company": "Example",
            "text": "Python and SQL",
            "url": "https://example.test/jobs/1",
        }

    async def apply_to_job(self, job_id, preferred_location=None):
        return {"job_id": job_id, "status": "SUBMITTED", "message": "Applied"}


def test_sync_service_bridges_async_placement_client(monkeypatch, tmp_path):
    monkeypatch.setattr("navigator.services.PlacementPortalClient", FakePortal)
    service = NavigatorService(str(tmp_path / "placement.db"))
    student = service.login_student("arun@college.edu", "secret")

    jobs = service.find_placement_opportunities(student.student_id)
    document = service.fetch_job_from_placement_portal(student.student_id, "job-1")
    result = service.apply_to_placement_job(student.student_id, "job-1")

    assert jobs[0]["job_id"] == "job-1"
    assert document.job_id == "job-1"
    assert result["status"] == "SUBMITTED"
    service.store.close()

"""Playwright tool for the forwarded mock placement portal."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator


class PlacementPortalError(RuntimeError):
    """Raised when the placement portal cannot complete a browser operation."""


class PlacementPortalClient:
    """Use the portal UI to read job descriptions and submit applications."""

    def __init__(
        self,
        base_url: str | None = None,
        student_id: str | None = None,
        password: str | None = None,
        headless: bool | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("PLACEMENT_PORTAL_URL", "http://127.0.0.1:3000")).rstrip("/")
        self.student_id = student_id or os.getenv("PLACEMENT_PORTAL_STUDENT_ID", "AU2027CSE001")
        self.password = password or os.getenv("PLACEMENT_PORTAL_PASSWORD", "student123")
        self.headless = headless if headless is not None else os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"

    @contextmanager
    def _page(self) -> Iterator[Any]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise PlacementPortalError(
                "Playwright is required for placement portal tools. Install requirements.txt "
                "and run `python -m playwright install chromium`."
            ) from exc

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.headless)
                page = browser.new_page()
                page.set_default_timeout(10_000)
                self._login(page)
                yield page
                browser.close()
        except PlaywrightTimeoutError as exc:
            raise PlacementPortalError(f"Placement portal timed out at {self.base_url}.") from exc
        except OSError as exc:
            raise PlacementPortalError(
                f"Could not reach placement portal at {self.base_url}. Start or forward the portal first."
            ) from exc

    def _login(self, page: Any) -> None:
        page.goto(f"{self.base_url}/login", wait_until="domcontentloaded")
        continue_button = page.get_by_role("button", name="Continue")
        if continue_button.count():
            continue_button.click()
            page.wait_for_load_state("domcontentloaded")
        if "/login" not in page.url:
            return
        page.get_by_test_id("student-id").fill(self.student_id)
        page.get_by_test_id("password").fill(self.password)
        page.get_by_test_id("login-button").click()
        page.wait_for_url(lambda url: "/login" not in url)

    def fetch_job(self, job_id: str) -> dict[str, Any]:
        """Read the complete visible JD from the portal."""
        with self._page() as page:
            return self._read_job(page, job_id)

    def _read_job(self, page: Any, job_id: str) -> dict[str, Any]:
        page.goto(f"{self.base_url}/jobs/{job_id}", wait_until="networkidle")
        required_skills = page.locator("#jd-required-skills").inner_text()
        preferred_skills = page.locator("#jd-preferred-skills").inner_text()
        return {
            "job_id": page.locator("#jd-id").inner_text().strip(),
            "company": page.locator("#jd-company").inner_text().strip(),
            "title": page.locator("#jd-role").inner_text().strip(),
            "description": page.locator("#jd-desc").inner_text().strip(),
            "required_skills": required_skills.strip(),
            "preferred_skills": preferred_skills.strip(),
            "text": "\n".join(
                part for part in (
                    page.locator("#jd-desc").inner_text().strip(),
                    page.locator("#jd-responsibilities").inner_text().strip(),
                    f"Required skills: {required_skills.strip()}",
                    f"Preferred skills: {preferred_skills.strip()}",
                ) if part
            ),
            "url": page.url,
            "eligible": page.get_by_test_id("eligibility-status").inner_text().strip().upper() == "ELIGIBLE",
            "eligibility_reason": page.get_by_test_id("eligibility-reason").inner_text().strip(),
        }

    def find_matching_jobs(self, target_role: str, target_skills: list[str], limit: int = 5) -> list[dict[str, Any]]:
        """Find portal drives matching the AI role and skill evidence."""
        role_terms = {term.lower() for term in target_role.split() if len(term) > 2}
        skill_terms = {skill.lower() for skill in target_skills if skill}
        with self._page() as page:
            page.goto(f"{self.base_url}/jobs", wait_until="networkidle")
            cards = page.locator("[data-testid^='job-card-']")
            cards.first.wait_for(state="visible")
            candidates: list[tuple[int, str]] = []
            for index in range(cards.count()):
                card = cards.nth(index)
                test_id = card.get_attribute("data-testid") or ""
                job_id = test_id.removeprefix("job-card-")
                card_text = card.inner_text().lower()
                score = sum(3 for term in role_terms if term in card_text)
                score += sum(2 for term in skill_terms if term in card_text)
                if score:
                    candidates.append((score, job_id))
            matches: list[dict[str, Any]] = []
            for score, job_id in sorted(candidates, reverse=True)[:limit]:
                job = self._read_job(page, job_id)
                job["match_score"] = score
                job["matched_skills"] = [skill for skill in target_skills if skill.lower() in job["text"].lower()]
                matches.append(job)
            return matches

    def apply_to_job(self, job_id: str, preferred_location: str | None = None) -> dict[str, Any]:
        """Confirm an eligible application through the portal UI."""
        with self._page() as page:
            page.goto(f"{self.base_url}/jobs/{job_id}", wait_until="networkidle")
            status = page.get_by_test_id("eligibility-status").inner_text().strip()
            if "ELIGIBLE" not in status.upper() or "NOT ELIGIBLE" in status.upper():
                reason = page.get_by_test_id("eligibility-reason").inner_text().strip()
                raise PlacementPortalError(f"Application blocked for {job_id}: {reason}")
            page.locator("#primary-apply-btn").click()
            if preferred_location:
                page.get_by_test_id("apply-location").select_option(preferred_location)
            page.get_by_test_id("confirm-application").click()
            page.get_by_test_id("application-success").wait_for(state="visible")
            return {
                "job_id": job_id,
                "status": "SUBMITTED",
                "message": page.get_by_test_id("application-success").inner_text().strip(),
                "url": page.url,
            }
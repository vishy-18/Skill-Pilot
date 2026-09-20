"""Playwright tool for the forwarded mock placement portal.

Browser work runs in a worker thread because Windows SelectorEventLoop cannot
spawn Playwright browser subprocesses from an async FastAPI request loop.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager
from typing import Any, Iterator

from slice.config import load_env


class PlacementPortalError(RuntimeError):
    """Raised when the placement portal cannot complete a browser operation."""


class PlacementPortalClient:
    """Use Playwright off the FastAPI event-loop thread on Windows."""

    def __init__(self, base_url: str | None = None, student_id: str | None = None, password: str | None = None, headless: bool | None = None) -> None:
        load_env()
        configured_url = base_url or os.getenv("PLACEMENT_PORTAL_URL", "").strip()
        if not configured_url:
            raise PlacementPortalError(
                "PLACEMENT_PORTAL_URL is not configured. Add the forwarded Mock Career Portal URL to .env, "
                "for example: PLACEMENT_PORTAL_URL=https://your-tunnel.devtunnels.ms"
            )
        self.base_url = configured_url.rstrip("/")
        self.student_id = student_id or os.getenv("PLACEMENT_PORTAL_STUDENT_ID", "AU2027CSE001")
        self.password = password or os.getenv("PLACEMENT_PORTAL_PASSWORD", "student123")
        self.headless = headless if headless is not None else os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"

    def _resolve_browser_url(self) -> str:
        """Resolve the URL that Playwright should navigate to.

        Use the configured forwarded portal by default. A local URL can be
        selected explicitly for a locally running mock portal.

        Priority:
        1. PLACEMENT_PORTAL_LOCAL_URL env-var (explicit override)
        2. Fall back to the configured base_url as-is
        """
        import re

        local_override = os.getenv("PLACEMENT_PORTAL_LOCAL_URL", "").strip()
        if local_override:
            return local_override.rstrip("/")

        return self.base_url

    @contextmanager
    def _page(self) -> Iterator[Any]:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise PlacementPortalError("Playwright is required. Run `python -m pip install -r requirements.txt` and `python -m playwright install chromium`.") from exc
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.headless)
                try:
                    page = browser.new_page()
                    page.set_default_timeout(30_000)
                    self._login(page)
                    yield page
                finally:
                    browser.close()
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            raise PlacementPortalError(f"Placement portal browser operation failed at {self.base_url}: {exc}") from exc
        except OSError as exc:
            raise PlacementPortalError(f"Could not reach placement portal at {self.base_url}. Start or forward the portal first.") from exc

    def _login(self, page: Any) -> None:
        browser_url = self._resolve_browser_url()

        page.goto(f"{browser_url}/login", wait_until="domcontentloaded")

        # Handle devtunnel interstitial "Continue" page (for non-OAuth tunnels)
        continue_button = page.get_by_role("button", name="Continue")
        if continue_button.count():
            continue_button.click()
            page.wait_for_load_state("domcontentloaded")

        if "/login" not in page.url:
            return

        # Wait for the login form to be fully rendered before interacting
        page.get_by_test_id("student-id").wait_for(state="visible", timeout=30_000)

        page.get_by_test_id("student-id").fill(self.student_id)
        page.get_by_test_id("password").fill(self.password)
        page.get_by_test_id("login-button").click()
        page.wait_for_url(lambda url: "/login" not in url, timeout=30_000)

    def _fetch_job_sync(self, job_id: str) -> dict[str, Any]:
        with self._page() as page:
            return self._read_job(page, job_id)

    async def fetch_job(self, job_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._fetch_job_sync, job_id)

    def _read_job(self, page: Any, job_id: str) -> dict[str, Any]:
        browser_url = self._resolve_browser_url()
        page.goto(f"{browser_url}/jobs/{job_id}", wait_until="networkidle")
        required = page.locator("#jd-required-skills").inner_text().strip()
        preferred = page.locator("#jd-preferred-skills").inner_text().strip()
        description = page.locator("#jd-desc").inner_text().strip()
        responsibilities = page.locator("#jd-responsibilities").inner_text().strip()
        status = page.get_by_test_id("eligibility-status").inner_text().strip().upper()
        return {
            "job_id": page.locator("#jd-id").inner_text().strip(), "company": page.locator("#jd-company").inner_text().strip(),
            "title": page.locator("#jd-role").inner_text().strip(), "description": description,
            "required_skills": required, "preferred_skills": preferred,
            "text": "\n".join(part for part in (description, responsibilities, f"Required skills: {required}", f"Preferred skills: {preferred}") if part),
            "url": page.url, "eligible": status == "ELIGIBLE",
            "eligibility_reason": page.get_by_test_id("eligibility-reason").inner_text().strip(),
        }

    def _find_matching_jobs_sync(self, target_role: str, target_skills: list[str], limit: int) -> list[dict[str, Any]]:
        role_terms = {term.lower() for term in target_role.split() if len(term) > 2}
        skill_terms = {skill.lower() for skill in target_skills if skill}
        with self._page() as page:
            browser_url = self._resolve_browser_url()
            page.goto(f"{browser_url}/jobs", wait_until="networkidle")
            cards = page.locator("[data-testid^='job-card-']")
            cards.first.wait_for(state="visible")
            candidates: list[tuple[int, str]] = []
            for index in range(cards.count()):
                card = cards.nth(index)
                job_id = (card.get_attribute("data-testid") or "").removeprefix("job-card-")
                text = card.inner_text().lower()
                score = sum(3 for term in role_terms if term in text) + sum(2 for term in skill_terms if term in text)
                if score:
                    candidates.append((score, job_id))
            matches = []
            for score, job_id in sorted(candidates, reverse=True)[:limit]:
                job = self._read_job(page, job_id)
                job["match_score"] = score
                job["matched_skills"] = [skill for skill in target_skills if skill.lower() in job["text"].lower()]
                matches.append(job)
            return matches

    async def find_matching_jobs(self, target_role: str, target_skills: list[str], limit: int = 5) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._find_matching_jobs_sync, target_role, target_skills, limit)

    def _apply_to_job_sync(self, job_id: str, preferred_location: str | None) -> dict[str, Any]:
        with self._page() as page:
            browser_url = self._resolve_browser_url()
            page.goto(f"{browser_url}/jobs/{job_id}", wait_until="networkidle")
            status = page.get_by_test_id("eligibility-status").inner_text().strip().upper()
            if status != "ELIGIBLE":
                reason = page.get_by_test_id("eligibility-reason").inner_text().strip()
                raise PlacementPortalError(f"Application blocked for {job_id}: {reason}")
            page.locator("#primary-apply-btn").click()
            if preferred_location:
                page.get_by_test_id("apply-location").select_option(preferred_location)
            page.get_by_test_id("confirm-application").click()
            page.get_by_test_id("application-success").wait_for(state="visible")
            return {"job_id": job_id, "status": "SUBMITTED", "message": page.get_by_test_id("application-success").inner_text().strip(), "url": page.url}

    async def apply_to_job(self, job_id: str, preferred_location: str | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._apply_to_job_sync, job_id, preferred_location)


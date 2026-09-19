"""Async Playwright tool for the forwarded mock placement portal."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator


class PlacementPortalError(RuntimeError):
    """Raised when the placement portal cannot complete a browser operation."""


class PlacementPortalClient:
    """Use the portal UI with async Playwright from FastAPI request handlers."""

    def __init__(self, base_url: str | None = None, student_id: str | None = None, password: str | None = None, headless: bool | None = None) -> None:
        self.base_url = (base_url or os.getenv("PLACEMENT_PORTAL_URL", "http://127.0.0.1:3000")).rstrip("/")
        self.student_id = student_id or os.getenv("PLACEMENT_PORTAL_STUDENT_ID", "AU2027CSE001")
        self.password = password or os.getenv("PLACEMENT_PORTAL_PASSWORD", "student123")
        self.headless = headless if headless is not None else os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"

    @asynccontextmanager
    async def _page(self) -> AsyncIterator[Any]:
        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise PlacementPortalError("Playwright is required. Run `python -m pip install -r requirements.txt` and `python -m playwright install chromium`.") from exc
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=self.headless)
                try:
                    page = await browser.new_page()
                    page.set_default_timeout(10_000)
                    await self._login(page)
                    yield page
                finally:
                    await browser.close()
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            raise PlacementPortalError(f"Placement portal browser operation failed at {self.base_url}: {exc}") from exc
        except OSError as exc:
            raise PlacementPortalError(f"Could not reach placement portal at {self.base_url}. Start or forward the portal first.") from exc

    async def _login(self, page: Any) -> None:
        await page.goto(f"{self.base_url}/login", wait_until="domcontentloaded")
        continue_button = page.get_by_role("button", name="Continue")
        if await continue_button.count():
            await continue_button.click()
            await page.wait_for_load_state("domcontentloaded")
        if "/login" not in page.url:
            return
        await page.get_by_test_id("student-id").fill(self.student_id)
        await page.get_by_test_id("password").fill(self.password)
        await page.get_by_test_id("login-button").click()
        await page.wait_for_url(lambda url: "/login" not in url)

    async def fetch_job(self, job_id: str) -> dict[str, Any]:
        async with self._page() as page:
            return await self._read_job(page, job_id)

    async def _read_job(self, page: Any, job_id: str) -> dict[str, Any]:
        await page.goto(f"{self.base_url}/jobs/{job_id}", wait_until="networkidle")
        required = await page.locator("#jd-required-skills").inner_text()
        preferred = await page.locator("#jd-preferred-skills").inner_text()
        description = await page.locator("#jd-desc").inner_text()
        responsibilities = await page.locator("#jd-responsibilities").inner_text()
        status = (await page.get_by_test_id("eligibility-status").inner_text()).strip().upper()
        return {
            "job_id": (await page.locator("#jd-id").inner_text()).strip(),
            "company": (await page.locator("#jd-company").inner_text()).strip(),
            "title": (await page.locator("#jd-role").inner_text()).strip(),
            "description": description.strip(),
            "required_skills": required.strip(),
            "preferred_skills": preferred.strip(),
            "text": "\n".join(part for part in (description.strip(), responsibilities.strip(), f"Required skills: {required.strip()}", f"Preferred skills: {preferred.strip()}") if part),
            "url": page.url,
            "eligible": status == "ELIGIBLE",
            "eligibility_reason": (await page.get_by_test_id("eligibility-reason").inner_text()).strip(),
        }

    async def find_matching_jobs(self, target_role: str, target_skills: list[str], limit: int = 5) -> list[dict[str, Any]]:
        role_terms = {term.lower() for term in target_role.split() if len(term) > 2}
        skill_terms = {skill.lower() for skill in target_skills if skill}
        async with self._page() as page:
            await page.goto(f"{self.base_url}/jobs", wait_until="networkidle")
            cards = page.locator("[data-testid^='job-card-']")
            await cards.first.wait_for(state="visible")
            candidates: list[tuple[int, str]] = []
            for index in range(await cards.count()):
                card = cards.nth(index)
                test_id = await card.get_attribute("data-testid") or ""
                job_id = test_id.removeprefix("job-card-")
                text = (await card.inner_text()).lower()
                score = sum(3 for term in role_terms if term in text) + sum(2 for term in skill_terms if term in text)
                if score:
                    candidates.append((score, job_id))
            matches: list[dict[str, Any]] = []
            for score, job_id in sorted(candidates, reverse=True)[:limit]:
                job = await self._read_job(page, job_id)
                job["match_score"] = score
                job["matched_skills"] = [skill for skill in target_skills if skill.lower() in job["text"].lower()]
                matches.append(job)
            return matches

    async def apply_to_job(self, job_id: str, preferred_location: str | None = None) -> dict[str, Any]:
        async with self._page() as page:
            await page.goto(f"{self.base_url}/jobs/{job_id}", wait_until="networkidle")
            status = (await page.get_by_test_id("eligibility-status").inner_text()).strip().upper()
            if status != "ELIGIBLE":
                reason = await page.get_by_test_id("eligibility-reason").inner_text()
                raise PlacementPortalError(f"Application blocked for {job_id}: {reason.strip()}")
            await page.locator("#primary-apply-btn").click()
            if preferred_location:
                await page.get_by_test_id("apply-location").select_option(preferred_location)
            await page.get_by_test_id("confirm-application").click()
            await page.get_by_test_id("application-success").wait_for(state="visible")
            return {"job_id": job_id, "status": "SUBMITTED", "message": (await page.get_by_test_id("application-success").inner_text()).strip(), "url": page.url}

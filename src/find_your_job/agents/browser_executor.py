from __future__ import annotations

from pathlib import Path
from typing import Callable

from .base import Agent, AgentResult
from find_your_job.models import BrowserExecutionResult, BrowserTask

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None


class BrowserExecutorAgent(Agent):
    def __init__(
        self,
        screenshot_dir: str = "artifacts/screenshots",
        headless: bool = True,
        timeout_ms: int = 15000,
        event_sink: Callable[[dict], None] | None = None,
    ) -> None:
        super().__init__("browser_executor_agent")
        self.screenshot_dir = Path(screenshot_dir)
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.event_sink = event_sink

    def run(self, tasks: list[BrowserTask], submit: bool = False) -> AgentResult[list[BrowserExecutionResult]]:
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._emit({
            "kind": "session",
            "code": "session_start",
            "data": {"mode": "headed" if not self.headless else "headless"},
            "message": f"Browser executor starting in {'headed' if not self.headless else 'headless'} mode."
        })

        if sync_playwright is None:
            results = [self._dependency_missing(task) for task in tasks]
            return AgentResult(agent_name=self.name, payload=results)

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=self.headless)
                self._emit({"kind": "session", "code": "session_launch_ok", "data": {}, "message": "Chromium launched successfully."})
            except Exception as exc:
                results = [self._launch_failed(task, exc) for task in tasks]
                return AgentResult(agent_name=self.name, payload=results)

            try:
                results = [self._execute_task(browser, task, submit=submit) for task in tasks]
            finally:
                browser.close()

        return AgentResult(agent_name=self.name, payload=results)

    def _execute_task(self, browser, task: BrowserTask, submit: bool) -> BrowserExecutionResult:
        mistakes: list[str] = []
        screenshots: list[str] = []
        self._emit({
            "kind": "task",
            "job_id": task.job_id,
            "code": "open_page",
            "data": {"url": task.application_url},
            "message": f"Opening application page: {task.application_url}"
        })

        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(self.timeout_ms)

        try:
            page.goto(task.application_url, wait_until="domcontentloaded")
            if task.wait_for_selector:
                self._emit({
                    "kind": "task",
                    "job_id": task.job_id,
                    "code": "wait_marker",
                    "data": {"selector": task.wait_for_selector},
                    "message": f"Waiting for page marker: {task.wait_for_selector}"
                })
                page.wait_for_selector(task.wait_for_selector)

            screenshots.append(self._capture(page, task.job_id, "loaded"))
            mistakes.extend(self._fill_fields(page, task))
            mistakes.extend(self._upload_files(page, task))

            if submit:
                mistakes.extend(self._submit(page, task))

            screenshots.append(self._capture(page, task.job_id, "final"))
        except PlaywrightTimeoutError as exc:
            mistakes.append(f"Playwright timeout while processing {task.application_url}: {exc}")
            self._emit({"kind": "error", "job_id": task.job_id, "message": mistakes[-1]})
        except Exception as exc:  # pragma: no cover
            mistakes.append(f"Playwright execution failed: {exc}")
            self._emit({"kind": "error", "job_id": task.job_id, "message": mistakes[-1]})
        finally:
            context.close()

        success = not mistakes
        self._emit({
            "kind": "task",
            "job_id": task.job_id,
            "code": "task_done" if success else "task_issues",
            "data": {},
            "message": f"Browser task {'completed' if success else 'finished with issues'}."
        })
        return BrowserExecutionResult(
            job_id=task.job_id,
            success=success,
            screenshots=screenshots,
            mistakes=mistakes,
            submitted=submit and success,
        )

    def _fill_fields(self, page, task: BrowserTask) -> list[str]:
        mistakes: list[str] = []
        for field_name, value in task.form_fields.items():
            selector = task.field_selectors.get(field_name)
            if not selector:
                mistakes.append(f"Missing selector for field '{field_name}'.")
                self._emit({"kind": "error", "job_id": task.job_id, "message": mistakes[-1]})
                continue
            try:
                locator = page.locator(selector).first
                self._emit({
                    "kind": "task",
                    "job_id": task.job_id,
                    "code": "locate_field",
                    "data": {"field": field_name, "selector": selector},
                    "message": f"Locating field '{field_name}' with {selector}"
                })
                locator.wait_for(state="visible")
                tag_name = (locator.evaluate("el => el.tagName") or "").lower()
                input_type = ""
                if tag_name == "input":
                    input_type = (locator.get_attribute("type") or "").lower()

                if tag_name == "select":
                    locator.select_option(label=value)
                elif input_type in {"checkbox", "radio"}:
                    should_check = value.strip().lower() in {"true", "1", "yes", "checked"}
                    if should_check:
                        locator.check()
                    else:
                        locator.uncheck()
                else:
                    locator.fill(value)
                self._emit({
                    "kind": "task",
                    "job_id": task.job_id,
                    "code": "filled_field",
                    "data": {"field": field_name},
                    "message": f"Filled field '{field_name}'."
                })
            except Exception as exc:
                mistakes.append(f"Failed to fill '{field_name}' using {selector}: {exc}")
                self._emit({"kind": "error", "job_id": task.job_id, "message": mistakes[-1]})
        return mistakes

    def _upload_files(self, page, task: BrowserTask) -> list[str]:
        mistakes: list[str] = []
        for field_name, file_path in task.files_to_upload.items():
            selector = task.upload_selectors.get(field_name)
            resolved = Path(file_path)
            if not selector:
                mistakes.append(f"Missing upload selector for file field '{field_name}'.")
                self._emit({"kind": "error", "job_id": task.job_id, "message": mistakes[-1]})
                continue
            if not resolved.exists():
                mistakes.append(f"Upload path for {field_name} does not exist: {file_path}")
                self._emit({"kind": "error", "job_id": task.job_id, "message": mistakes[-1]})
                continue
            try:
                locator = page.locator(selector).first
                self._emit({
                    "kind": "task",
                    "job_id": task.job_id,
                    "code": "uploading_file",
                    "data": {"field": field_name, "filename": resolved.name},
                    "message": f"Uploading {resolved.name} into '{field_name}'."
                })
                locator.set_input_files(str(resolved.resolve()))
                self._emit({
                    "kind": "task",
                    "job_id": task.job_id,
                    "code": "uploaded_file",
                    "data": {"field": field_name, "filename": resolved.name},
                    "message": f"Uploaded file for '{field_name}'."
                })
            except Exception as exc:
                mistakes.append(f"Failed to upload '{field_name}' using {selector}: {exc}")
                self._emit({"kind": "error", "job_id": task.job_id, "message": mistakes[-1]})
        return mistakes

    def _submit(self, page, task: BrowserTask) -> list[str]:
        if not task.submit_selector:
            message = "Submit requested but no submit selector was configured."
            self._emit({"kind": "error", "job_id": task.job_id, "message": message})
            return [message]
        try:
            locator = page.locator(task.submit_selector).first
            self._emit({
                "kind": "task",
                "job_id": task.job_id,
                "code": "wait_submit",
                "data": {"selector": task.submit_selector},
                "message": f"Waiting for submit control: {task.submit_selector}"
            })
            locator.wait_for(state="visible")
            locator.click()
            page.wait_for_load_state("networkidle")
            self._emit({"kind": "task", "job_id": task.job_id, "code": "submit_done", "data": {}, "message": "Submit action executed."})
            return []
        except Exception as exc:
            message = f"Failed to submit using {task.submit_selector}: {exc}"
            self._emit({"kind": "error", "job_id": task.job_id, "message": message})
            return [message]

    def _capture(self, page, job_id: str, suffix: str) -> str:
        screenshot_path = self.screenshot_dir / f"{job_id}-{suffix}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        self._emit({
            "kind": "screenshot",
            "job_id": job_id,
            "code": "capture",
            "data": {"filename": screenshot_path.name},
            "message": f"Captured screenshot: {screenshot_path.name}",
            "path": f"/{screenshot_path.as_posix()}"
        })
        return str(screenshot_path)

    def _dependency_missing(self, task: BrowserTask) -> BrowserExecutionResult:
        self._emit({"kind": "error", "job_id": task.job_id, "message": "Playwright is not installed. Run `pip install -e \".[browser]\"` and `playwright install`."})
        return BrowserExecutionResult(
            job_id=task.job_id,
            success=False,
            screenshots=[],
            mistakes=[
                "Playwright is not installed. Run `pip install -e \".[browser]\"` and `playwright install`.",
            ],
            submitted=False,
        )

    def _launch_failed(self, task: BrowserTask, exc: Exception) -> BrowserExecutionResult:
        self._emit({"kind": "error", "job_id": task.job_id, "message": f"Playwright browser launch failed: {exc}"})
        return BrowserExecutionResult(
            job_id=task.job_id,
            success=False,
            screenshots=[],
            mistakes=[
                f"Playwright browser launch failed: {exc}",
            ],
            submitted=False,
        )

    def _emit(self, event: dict) -> None:
        if self.event_sink:
            self.event_sink(event)

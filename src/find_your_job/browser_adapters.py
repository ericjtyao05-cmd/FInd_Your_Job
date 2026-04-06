from __future__ import annotations

from urllib.parse import urlparse

from find_your_job.models import ApplicationPackage, BrowserTask, CandidateProfile, JobPosting


class BrowserTaskBuilder:
    def build(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        application: ApplicationPackage,
    ) -> BrowserTask:
        host = urlparse(job.url).netloc.lower()
        source = job.source.lower()

        if "greenhouse" in host or "greenhouse" in source:
            return self._greenhouse_task(candidate, job, application)
        if "lever" in host or "lever" in source:
            return self._lever_task(candidate, job, application)
        if "workday" in host or "workday" in source:
            return self._workday_task(candidate, job, application)
        return self._generic_task(candidate, job, application)

    def _greenhouse_task(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        application: ApplicationPackage,
    ) -> BrowserTask:
        return BrowserTask(
            job_id=application.job_id,
            application_url=job.url,
            form_fields=self._base_form_fields(candidate, application),
            files_to_upload=self._base_uploads(candidate),
            field_selectors={
                "name": 'input[name="first_name"]',
                "email": 'input[name="email"]',
                "phone": 'input[name="phone"]',
                "location": 'input[name="location"]',
                "cover_letter": 'textarea[name="cover_letter"]',
            },
            upload_selectors={
                "resume": 'input[name="resume"]',
            },
            submit_selector='button[type="submit"]',
            wait_for_selector="#application_form",
            notes=["Greenhouse adapter selected based on source/url match."],
        )

    def _lever_task(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        application: ApplicationPackage,
    ) -> BrowserTask:
        return BrowserTask(
            job_id=application.job_id,
            application_url=job.url,
            form_fields=self._base_form_fields(candidate, application),
            files_to_upload=self._base_uploads(candidate),
            field_selectors={
                "name": 'input[name="name"]',
                "email": 'input[name="email"]',
                "phone": 'input[name="phone"]',
                "location": 'input[name="location"]',
                "cover_letter": 'textarea[name="comments"]',
            },
            upload_selectors={
                "resume": 'input[name="resume"]',
            },
            submit_selector='button[type="submit"]',
            wait_for_selector='form',
            notes=["Lever adapter selected based on source/url match."],
        )

    def _workday_task(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        application: ApplicationPackage,
    ) -> BrowserTask:
        return BrowserTask(
            job_id=application.job_id,
            application_url=job.url,
            form_fields=self._base_form_fields(candidate, application),
            files_to_upload=self._base_uploads(candidate),
            field_selectors={
                "email": 'input[type="email"]',
                "name": 'input[name*="name"], input[id*="name"]',
                "phone": 'input[type="tel"]',
                "location": 'input[name*="location"], input[id*="location"]',
                "cover_letter": 'textarea',
            },
            upload_selectors={
                "resume": 'input[type="file"]',
            },
            submit_selector='button[data-automation-id="bottom-navigation-next-button"], button[type="submit"]',
            wait_for_selector='form, [data-automation-id="pageHeader"]',
            notes=[
                "Workday adapter selected based on source/url match.",
                "Workday forms vary heavily; selectors may need per-company overrides.",
            ],
        )

    def _generic_task(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        application: ApplicationPackage,
    ) -> BrowserTask:
        return BrowserTask(
            job_id=application.job_id,
            application_url=job.url,
            form_fields=self._base_form_fields(candidate, application),
            files_to_upload=self._base_uploads(candidate),
            field_selectors={
                "name": 'input[name="name"], input[type="text"]',
                "email": 'input[name="email"], input[type="email"]',
                "phone": 'input[name="phone"], input[type="tel"]',
                "location": 'input[name="location"]',
                "cover_letter": 'textarea[name="cover_letter"], textarea',
            },
            upload_selectors={
                "resume": 'input[type="file"]',
            },
            submit_selector='button[type="submit"], input[type="submit"]',
            wait_for_selector="form, body",
            notes=["Generic adapter selected because no known board type matched."],
        )

    def _base_form_fields(self, candidate: CandidateProfile, application: ApplicationPackage) -> dict[str, str]:
        return {
            "name": candidate.name,
            "email": f"{candidate.name.lower().replace(' ', '.')}@example.com",
            "phone": "+44 7700 900123",
            "location": candidate.preferred_locations[0] if candidate.preferred_locations else "",
            "cover_letter": application.cover_letter,
        }

    def _base_uploads(self, candidate: CandidateProfile) -> dict[str, str]:
        return {
            "resume": candidate.resume_path or "examples/resume.txt",
        }

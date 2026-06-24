"""
GitHub committer: pushes the daily markdown report to the configured repository.

Uses PyGithub (github.Github). Requires GITHUB_TOKEN and GITHUB_REPO
(format: "username/repo-name") to be set in the environment.

The report is committed at:
  reports/YYYY-MM-DD.md

If the file already exists for that date it is updated in-place.
Returns the commit SHA on success, None on failure or when not configured.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_COMMIT_MESSAGE = "research: daily report {date}"


class GitCommitter:

    def __init__(self, settings) -> None:
        self.settings = settings

    def commit_report(self, report_path: str, run_date: date) -> Optional[str]:
        """
        Commit the markdown report at `report_path` to GitHub.
        Returns commit SHA, or None if not configured / failed.
        """
        if not self.settings.github_token:
            logger.info("GitHub commit skipped — GITHUB_TOKEN not set")
            return None
        if not self.settings.github_repo:
            logger.info("GitHub commit skipped — GITHUB_REPO not set")
            return None

        try:
            content = Path(report_path).read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Cannot read report file %s: %s", report_path, e)
            return None

        remote_path = f"reports/{run_date}.md"
        commit_msg = _COMMIT_MESSAGE.format(date=run_date)

        try:
            from github import Github, GithubException

            gh = Github(self.settings.github_token)
            repo = gh.get_repo(self.settings.github_repo)
            branch = self.settings.github_branch or "main"

            try:
                existing = repo.get_contents(remote_path, ref=branch)
                result = repo.update_file(
                    path=remote_path,
                    message=commit_msg,
                    content=content,
                    sha=existing.sha,
                    branch=branch,
                )
            except GithubException as e:
                if e.status == 404:
                    result = repo.create_file(
                        path=remote_path,
                        message=commit_msg,
                        content=content,
                        branch=branch,
                    )
                else:
                    raise

            sha = result["commit"].sha
            logger.info(
                "Report committed to %s/%s (SHA: %s)",
                self.settings.github_repo, remote_path, sha[:8],
            )
            return sha

        except Exception as e:
            logger.error("GitHub commit failed: %s", e)
            return None

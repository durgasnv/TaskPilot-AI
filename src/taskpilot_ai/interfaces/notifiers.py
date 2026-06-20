"""
Push notification implementations for Dev4's NotifierProtocol.

CLINotifier  — prints a formatted terminal alert (always available).
SlackNotifier — posts to a Slack incoming-webhook URL via stdlib urllib.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone


class CLINotifier:
    """Prints a formatted, easy-to-spot terminal alert."""

    _BORDER = "=" * 60

    def notify(self, message: str, channel: str = "cli") -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        print(f"\n{self._BORDER}")
        print(f"  !! TASKPILOT ALERT [{ts}] !!")
        print(f"  {message}")
        print(f"{self._BORDER}\n", flush=True)


class SlackNotifier:
    """
    Posts a plain-text alert to a Slack incoming-webhook URL.

    The webhook URL can be supplied directly or via the SLACK_WEBHOOK_URL
    environment variable.  Falls back to CLINotifier output if no URL is
    configured so the system never silently swallows an alert.
    """

    def __init__(self, webhook_url: str | None = None) -> None:
        self._url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")
        self._cli = CLINotifier()

    def notify(self, message: str, channel: str = "cli") -> None:
        self._cli.notify(message, channel)  # always echo to terminal too

        if not self._url:
            return

        payload = json.dumps({"text": f":rotating_light: *TaskPilot Alert*\n{message}"}).encode()
        req = urllib.request.Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5):
                pass
        except (urllib.error.URLError, OSError) as exc:
            print(f"[SlackNotifier] webhook delivery failed: {exc}")


def build_notifier(slack_webhook_url: str | None = None) -> CLINotifier | SlackNotifier:
    """Return the best available notifier based on configuration."""
    if slack_webhook_url or os.environ.get("SLACK_WEBHOOK_URL"):
        return SlackNotifier(slack_webhook_url)
    return CLINotifier()

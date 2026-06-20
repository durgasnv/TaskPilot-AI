"""Tests for Dev4 push notification implementations."""

import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from taskpilot_ai.interfaces.notifiers import CLINotifier, SlackNotifier, build_notifier
from taskpilot_ai.interfaces.protocols import NotifierProtocol


class TestCLINotifier(unittest.TestCase):
    def test_satisfies_protocol(self):
        assert isinstance(CLINotifier(), NotifierProtocol)

    def test_notify_prints_message(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            CLINotifier().notify("hello world")
        assert "hello world" in buf.getvalue()

    def test_notify_prints_alert_border(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            CLINotifier().notify("test alert")
        out = buf.getvalue()
        assert "TASKPILOT ALERT" in out
        assert "=" * 10 in out

    def test_channel_arg_accepted(self):
        CLINotifier().notify("msg", channel="slack")  # must not raise


class TestSlackNotifier(unittest.TestCase):
    def test_satisfies_protocol(self):
        assert isinstance(SlackNotifier(), NotifierProtocol)

    def test_no_webhook_skips_http(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf), patch("urllib.request.urlopen") as mock_open:
            SlackNotifier(webhook_url=None).notify("no webhook")
        mock_open.assert_not_called()

    def test_always_echoes_to_cli(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            SlackNotifier(webhook_url=None).notify("echo me")
        assert "echo me" in buf.getvalue()

    def test_posts_to_webhook_when_configured(self):
        with patch("urllib.request.urlopen") as mock_open, \
             patch("sys.stdout", io.StringIO()):
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            SlackNotifier(webhook_url="https://hooks.example.com/T1").notify("p1 fire")
        mock_open.assert_called_once()

    def test_webhook_failure_does_not_raise(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")), \
             patch("sys.stdout", io.StringIO()):
            SlackNotifier(webhook_url="https://hooks.example.com/bad").notify("fail ok")


class TestBuildNotifier(unittest.TestCase):
    def test_returns_cli_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            n = build_notifier()
        assert isinstance(n, CLINotifier)

    def test_returns_slack_when_url_provided(self):
        n = build_notifier(slack_webhook_url="https://hooks.example.com/T1")
        assert isinstance(n, SlackNotifier)

    def test_returns_slack_when_env_var_set(self):
        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.example.com/T2"}):
            n = build_notifier()
        assert isinstance(n, SlackNotifier)


if __name__ == "__main__":
    unittest.main(verbosity=2)

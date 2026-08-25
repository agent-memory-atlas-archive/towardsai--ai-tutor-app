import os
import unittest
from unittest.mock import patch

from app import alerts


class SendOpsAlertTest(unittest.TestCase):
    def setUp(self) -> None:
        alerts._LAST_SENT.clear()
        self.addCleanup(alerts._LAST_SENT.clear)

    def test_without_webhook_url_it_logs_only(self) -> None:
        with patch.dict(os.environ, {alerts.ALERT_WEBHOOK_ENV: ""}, clear=False):
            self.assertFalse(alerts.send_ops_alert("account-state", "no funds"))

    def test_throttles_repeat_kinds_but_not_distinct_kinds(self) -> None:
        posts: list[dict] = []
        with (
            patch.dict(
                os.environ,
                {alerts.ALERT_WEBHOOK_ENV: "https://example.invalid/hook"},
                clear=False,
            ),
            patch(
                "app.alerts.httpx.post",
                side_effect=lambda url, json, timeout: posts.append(json),
            ),
        ):
            self.assertTrue(alerts.send_ops_alert("account-state", "first"))
            self.assertFalse(alerts.send_ops_alert("account-state", "repeat"))
            self.assertTrue(alerts.send_ops_alert("provider-outage", "other"))
        self.assertEqual(len(posts), 2)
        self.assertIn("account-state", posts[0]["text"])
        self.assertIn("first", posts[0]["text"])

    def test_failed_post_clears_the_throttle_for_retry(self) -> None:
        attempts = {"count": 0}

        def flaky_post(url, json, timeout):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("webhook unreachable")

        with (
            patch.dict(
                os.environ,
                {alerts.ALERT_WEBHOOK_ENV: "https://example.invalid/hook"},
                clear=False,
            ),
            patch("app.alerts.httpx.post", side_effect=flaky_post),
        ):
            self.assertFalse(alerts.send_ops_alert("account-state", "first"))
            self.assertTrue(alerts.send_ops_alert("account-state", "retry"))
        self.assertEqual(attempts["count"], 2)

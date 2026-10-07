import importlib.util
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("hook", Path(__file__).with_name("runcat-hook.py"))
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class UsageTests(unittest.TestCase):
    def test_token_units(self):
        for value, expected in [(0, "0"), (999, "999"), (1000, "1K"),
                                (12500, "12.5K"), (41176231, "41.18M"),
                                (1234567890, "1.23B")]:
            self.assertEqual(hook.format_tokens(value), expected)

    def test_calendar_boundaries_and_zero_days(self):
        rows = [{"date": day, "totalTokens": tokens} for day, tokens in [
            ("2026-09-07", 999), ("2026-09-08", 30),
            ("2026-09-30", 20), ("2026-10-01", 10),
            ("2026-10-07", 60), ("2026-10-08", 999),
        ]]
        metrics = hook.usage_metrics({"daily": rows}, date(2026, 10, 7))
        self.assertEqual([m["formattedValue"] for m in metrics], ["60", "70", "120", "4"])
        self.assertTrue(all("normalizedValue" not in m for m in metrics))

    def test_empty_history_has_no_artificial_usage(self):
        metrics = hook.usage_metrics({"daily": []}, date(2026, 10, 7))
        self.assertEqual([m["formattedValue"] for m in metrics], ["0"] * 4)

    def test_invalid_report_is_not_zero_usage(self):
        for report in ({}, {"daily": [{"date": "2026-10-07", "totalTokens": -1}]}):
            with self.assertRaises(ValueError):
                hook.usage_metrics(report, date(2026, 10, 7))

    def test_countdown_progress_and_expiry(self):
        row = {"_resetAt": 10000, "_windowSeconds": 7200}
        hook.update_countdown(row, 6400)
        self.assertEqual(row["normalizedValue"], 0.5)
        self.assertEqual(row["formattedValue"], "1h 0m remaining")
        hook.update_countdown(row, 10001)
        self.assertEqual(row["normalizedValue"], 0)
        self.assertIn("awaiting", row["formattedValue"])

    def test_timer_keeps_usage_timestamp(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "usage.json"
            original = {"lastUpdatedDate": "2026-10-07T00:00:00Z", "metrics": [
                {"title": "7d reset", "_resetAt": 1, "_windowSeconds": 604800},
                {"title": "Today tokens", "formattedValue": "123"},
            ]}
            output.write_text(json.dumps(original))
            with patch.object(hook, "OUT", output):
                hook.refresh_countdowns()
            updated = json.loads(output.read_text())
            self.assertEqual(updated["lastUpdatedDate"], original["lastUpdatedDate"])
            self.assertEqual(updated["metrics"][1], original["metrics"][1])

    def test_failed_statistics_preserve_quota_and_mark_unavailable(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "usage.json"
            output.write_text(json.dumps({"metrics": [
                {"title": "7d", "formattedValue": "20%"},
                {"title": "7d reset", "formattedValue": "10-10 12:00"},
                {"title": "7d tokens", "formattedValue": "999"},
            ]}))
            with patch.object(hook, "OUT", output), patch.object(hook, "load_usage_metrics", side_effect=RuntimeError("offline failure")):
                hook.write_snapshot({})
            metrics = json.loads(output.read_text())["metrics"]
            titles = [row["title"] for row in metrics]
            self.assertIn("7d reset", titles)
            self.assertIn("Quota status", titles)
            self.assertIn("Token statistics", titles)
            self.assertNotIn("7d tokens", titles)
            self.assertNotIn("Model", titles)
            self.assertNotIn("Context", titles)


if __name__ == "__main__":
    unittest.main()

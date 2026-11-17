import os
import unittest
from unittest.mock import patch

import pandas as pd

from market_calendar import create_api_server


class TestApiRateLimit(unittest.TestCase):
    def test_rejects_eleventh_request_without_upstream_calls(self):
        with patch.dict(os.environ, {
            "RATELIMIT_STORAGE_URI": "memory://",
            "RATELIMIT_REQUIRE_SHARED_STORAGE": "0",
        }):
            with patch("market_calendar.StockMarketCalendar") as calendar_cls:
                calendar_cls.return_value.krx.get_holidays.return_value = pd.DataFrame()
                app = create_api_server()
                app.testing = True
                client = app.test_client()
                statuses = [
                    client.get("/calendar/holidays", environ_overrides={
                        "REMOTE_ADDR": "192.0.2.10",
                    }).status_code
                    for _ in range(11)
                ]
                self.assertEqual(statuses[:10], [200] * 10)
                self.assertEqual(statuses[10], 429)
                self.assertEqual(calendar_cls.return_value.krx.get_holidays.call_count, 10)

                # A separate client IP must not inherit the first client's quota.
                other = client.get("/calendar/holidays", environ_overrides={
                    "REMOTE_ADDR": "192.0.2.11",
                })
                self.assertEqual(other.status_code, 200)
                self.assertEqual(calendar_cls.return_value.krx.get_holidays.call_count, 11)

    def test_rejects_non_shared_storage_when_required(self):
        for uri in ("memory://", "memory:// ", "mongodb://localhost:27017", ""):
            with self.subTest(uri=uri):
                with patch.dict(os.environ, {
                    "RATELIMIT_STORAGE_URI": uri,
                    "RATELIMIT_REQUIRE_SHARED_STORAGE": "1",
                }):
                    with self.assertRaises(RuntimeError):
                        create_api_server()

    def test_rejects_empty_storage_uri_even_in_development(self):
        with patch.dict(os.environ, {
            "RATELIMIT_STORAGE_URI": "  ",
            "RATELIMIT_REQUIRE_SHARED_STORAGE": "0",
        }):
            with self.assertRaisesRegex(RuntimeError, "must not be empty"):
                create_api_server()


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from unittest.mock import patch

import pandas as pd

from market_calendar import create_api_server


class TestApiRateLimit(unittest.TestCase):
    def test_rejects_eleventh_request_without_upstream_calls(self):
        with patch.dict(os.environ, {"RATELIMIT_STORAGE_URI": "memory://"}, clear=False):
            with patch("market_calendar.StockMarketCalendar") as calendar_cls:
                calendar_cls.return_value.krx.get_holidays.return_value = pd.DataFrame()
                app = create_api_server()
                app.testing = True
                client = app.test_client()
                statuses = [client.get("/calendar/holidays").status_code for _ in range(11)]
                self.assertEqual(statuses[:10], [200] * 10)
                self.assertEqual(statuses[10], 429)
                self.assertEqual(calendar_cls.return_value.krx.get_holidays.call_count, 10)

    def test_rejects_memory_storage_when_shared_storage_required(self):
        with patch.dict(os.environ, {
            "RATELIMIT_STORAGE_URI": "memory://",
            "RATELIMIT_REQUIRE_SHARED_STORAGE": "1",
        }):
            with self.assertRaisesRegex(RuntimeError, "Shared rate-limit storage required"):
                create_api_server()


if __name__ == "__main__":
    unittest.main()

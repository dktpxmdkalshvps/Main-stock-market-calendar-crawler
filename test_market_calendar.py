import unittest
import pandas as pd
from unittest.mock import patch
from market_calendar import create_api_server

class TestMarketCalendarServer(unittest.TestCase):
    def setUp(self):
        self.app = create_api_server()
        if self.app is None:
            self.skipTest("Flask is not installed")
        self.client = self.app.test_client()

    @patch('market_calendar.StockMarketCalendar.fetch_all')
    def test_rate_limiting(self, mock_fetch_all):
        mock_fetch_all.return_value = {}
        # The limit is 10 per minute, so we should be blocked after 10 requests.
        for i in range(12):
            response = self.client.get("/calendar")
            if response.status_code == 429:
                break

        self.assertEqual(response.status_code, 429, f"Rate limit was not enforced at iteration {i}")

if __name__ == '__main__':
    unittest.main()

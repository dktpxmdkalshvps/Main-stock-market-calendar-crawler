import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
from market_calendar import get_date_range

class TestMarketCalendar(unittest.TestCase):

    @patch('market_calendar.datetime')
    def test_get_date_range_both_none(self, mock_datetime):
        # Mock today's date to be a specific date
        mock_today = datetime(2024, 1, 1)
        mock_datetime.today.return_value = mock_today

        # When both are None, default is today and 7 days from today
        start, end = get_date_range(None, None)
        self.assertEqual(start, "20240101")
        self.assertEqual(end, "20240108")

    @patch('market_calendar.datetime')
    def test_get_date_range_only_start(self, mock_datetime):
        # Mock today's date
        mock_today = datetime(2024, 1, 1)
        mock_datetime.today.return_value = mock_today

        # When start is provided, it should be used. end should be 7 days from today.
        start, end = get_date_range("20231225", None)
        self.assertEqual(start, "20231225")
        self.assertEqual(end, "20240108")

    @patch('market_calendar.datetime')
    def test_get_date_range_only_end(self, mock_datetime):
        # Mock today's date
        mock_today = datetime(2024, 1, 1)
        mock_datetime.today.return_value = mock_today

        # When end is provided, it should be used. start should be today.
        start, end = get_date_range(None, "20240115")
        self.assertEqual(start, "20240101")
        self.assertEqual(end, "20240115")

    def test_get_date_range_both_provided(self):
        # When both are provided, no default logic should run.
        start, end = get_date_range("20231225", "20240115")
        self.assertEqual(start, "20231225")
        self.assertEqual(end, "20240115")

if __name__ == '__main__':
    unittest.main()

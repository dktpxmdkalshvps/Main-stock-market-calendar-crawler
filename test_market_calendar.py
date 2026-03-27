import sys
import unittest
from unittest.mock import MagicMock, patch

# Gracefully handle missing dependencies for testing environment
# Only mock modules that are actually missing to avoid polluting the test environment
dependencies = ['requests', 'bs4', 'pandas', 'openpyxl', 'pykrx', 'pandas_market_calendars', 'OpenDartReader', 'lxml']
for mod in dependencies:
    try:
        __import__(mod)
    except ImportError:
        sys.modules[mod] = MagicMock()

import market_calendar

class TestDartEarningsCalendar(unittest.TestCase):
    @patch('market_calendar.safe_get')
    def test_get_disclosure_list_non_000_status(self, mock_safe_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "010", "message": "API Limit Exceeded"}
        mock_safe_get.return_value = mock_resp

        calendar = market_calendar.DartEarningsCalendar(api_key='test_key')
        result = calendar.get_disclosure_list("20230101", "20230131")

        mock_safe_get.assert_called_once()

        if isinstance(result, MagicMock):
            # If pandas was mocked, verify pd.DataFrame was called to return an empty dataframe
            market_calendar.pd.DataFrame.assert_called_with()
        else:
            # If real pandas is available, verify the dataframe is empty
            self.assertTrue(result.empty)

if __name__ == '__main__':
    unittest.main()

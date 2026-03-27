import unittest
from unittest.mock import MagicMock, patch
import sys

class TestStockMarketCalendar(unittest.TestCase):

    def setUp(self):
        # To avoid module import errors and leaking global state permanently
        # we only mock the unavailable packages when running tests inside patch.dict
        self.mock_modules = {
            'requests': MagicMock(),
            'bs4': MagicMock(),
            'openpyxl': MagicMock(),
            'pykrx': MagicMock(),
            'pandas_market_calendars': MagicMock(),
            'OpenDartReader': MagicMock(),
            'lxml': MagicMock(),
            'flask': MagicMock(),
            'flask_limiter': MagicMock()
        }

        class MockPandas:
            DataFrame = MagicMock()
            to_datetime = MagicMock()

        self.mock_modules['pandas'] = MockPandas()

        self.patcher = patch.dict('sys.modules', self.mock_modules)
        self.patcher.start()

        # Now import the module under test inside the patched environment
        global StockMarketCalendar
        from market_calendar import StockMarketCalendar

    def tearDown(self):
        self.patcher.stop()

    @patch('market_calendar.get_date_range')
    def test_fetch_all_default_no_dart(self, mock_get_date_range):
        mock_get_date_range.return_value = ('20230101', '20230107')

        # Initialize calendar without DART API key
        cal = StockMarketCalendar()

        # Mock all underlying calendar classes
        cal.naver = MagicMock()
        cal.naver.get_all_earnings.return_value = MagicMock()

        cal.kind = MagicMock()
        cal.kind.get_ipo_schedule.return_value = MagicMock()

        cal.yahoo = MagicMock()
        cal.yahoo.get_week_earnings.return_value = MagicMock()

        cal.investing = MagicMock()
        cal.investing.get_calendar.return_value = MagicMock()

        cal.krx = MagicMock()
        cal.krx.get_holidays.return_value = MagicMock()

        # DART should be None
        self.assertIsNone(cal.dart)

        # Call fetch_all with default sources
        results = cal.fetch_all()

        # Verify mocked methods were called
        cal.naver.get_all_earnings.assert_called_once_with(pages=3)
        cal.kind.get_ipo_schedule.assert_called_once_with('20230101', '20230107')
        cal.yahoo.get_week_earnings.assert_called_once()
        cal.investing.get_calendar.assert_called_once_with('20230101', '20230107', countries=[5, 11])
        cal.krx.get_holidays.assert_called_once()

        # Verify correct keys exist in results
        self.assertIn("국내_실적발표", results)
        self.assertIn("공모주_청약", results)
        self.assertIn("미국_실적발표", results)
        self.assertIn("글로벌_경제지표", results)
        self.assertIn("증시_휴장일", results)
        self.assertNotIn("DART_실적발표", results)

    @patch('market_calendar.get_date_range')
    def test_fetch_all_default_with_dart(self, mock_get_date_range):
        mock_get_date_range.return_value = ('20230101', '20230107')

        # Initialize calendar with DART API key
        cal = StockMarketCalendar(dart_api_key="test_key")

        # Mock all underlying calendar classes
        cal.naver = MagicMock()
        cal.kind = MagicMock()
        cal.yahoo = MagicMock()
        cal.investing = MagicMock()
        cal.krx = MagicMock()
        cal.dart = MagicMock()
        cal.dart.get_disclosure_list.return_value = MagicMock()

        # Call fetch_all with default sources
        results = cal.fetch_all()

        # Verify DART method was called
        cal.dart.get_disclosure_list.assert_called_once_with('20230101', '20230107')

        # Verify correct keys exist in results
        self.assertIn("국내_실적발표", results)
        self.assertIn("공모주_청약", results)
        self.assertIn("미국_실적발표", results)
        self.assertIn("글로벌_경제지표", results)
        self.assertIn("증시_휴장일", results)
        self.assertIn("DART_실적발표", results)

    @patch('market_calendar.get_date_range')
    def test_fetch_all_specific_sources(self, mock_get_date_range):
        mock_get_date_range.return_value = ('20230101', '20230107')

        cal = StockMarketCalendar()

        # Mock all underlying calendar classes
        cal.naver = MagicMock()
        cal.kind = MagicMock()
        cal.yahoo = MagicMock()
        cal.investing = MagicMock()
        cal.krx = MagicMock()

        # Call fetch_all with specific sources
        results = cal.fetch_all(sources=["yahoo", "krx"])

        # Verify only specific mocked methods were called
        cal.naver.get_all_earnings.assert_not_called()
        cal.kind.get_ipo_schedule.assert_not_called()
        cal.yahoo.get_week_earnings.assert_called_once()
        cal.investing.get_calendar.assert_not_called()
        cal.krx.get_holidays.assert_called_once()

        # Verify correct keys exist in results
        self.assertNotIn("국내_실적발표", results)
        self.assertNotIn("공모주_청약", results)
        self.assertIn("미국_실적발표", results)
        self.assertNotIn("글로벌_경제지표", results)
        self.assertIn("증시_휴장일", results)

if __name__ == '__main__':
    unittest.main()

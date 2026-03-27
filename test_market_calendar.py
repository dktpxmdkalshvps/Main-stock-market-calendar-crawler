import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from market_calendar import NaverEarningsCalendar

class TestNaverEarningsCalendar(unittest.TestCase):
    def setUp(self):
        self.calendar = NaverEarningsCalendar()

    @patch.object(NaverEarningsCalendar, '_get_from_yonhap')
    @patch.object(NaverEarningsCalendar, '_get_from_fnguide')
    @patch.object(NaverEarningsCalendar, '_get_from_wisereport')
    def test_get_earnings_by_month_wisereport_success(self, mock_wise, mock_fn, mock_yonhap):
        # Setup
        df_wise = pd.DataFrame([{"발표일": "2023-10-25"}])
        mock_wise.return_value = df_wise

        # Execute
        result = self.calendar.get_earnings_by_month(2023, 10)

        # Verify
        pd.testing.assert_frame_equal(result, df_wise)
        mock_wise.assert_called_once_with(2023, 10)
        mock_fn.assert_not_called()
        mock_yonhap.assert_not_called()

    @patch.object(NaverEarningsCalendar, '_get_from_yonhap')
    @patch.object(NaverEarningsCalendar, '_get_from_fnguide')
    @patch.object(NaverEarningsCalendar, '_get_from_wisereport')
    def test_get_earnings_by_month_fnguide_success(self, mock_wise, mock_fn, mock_yonhap):
        # Setup
        mock_wise.return_value = pd.DataFrame()
        df_fn = pd.DataFrame([{"발표일": "2023-10-26"}])
        mock_fn.return_value = df_fn

        # Execute
        result = self.calendar.get_earnings_by_month(2023, 10)

        # Verify
        pd.testing.assert_frame_equal(result, df_fn)
        mock_wise.assert_called_once_with(2023, 10)
        mock_fn.assert_called_once_with(2023, 10)
        mock_yonhap.assert_not_called()

    @patch.object(NaverEarningsCalendar, '_get_from_yonhap')
    @patch.object(NaverEarningsCalendar, '_get_from_fnguide')
    @patch.object(NaverEarningsCalendar, '_get_from_wisereport')
    def test_get_earnings_by_month_yonhap_success(self, mock_wise, mock_fn, mock_yonhap):
        # Setup
        mock_wise.return_value = pd.DataFrame()
        mock_fn.return_value = pd.DataFrame()
        df_yonhap = pd.DataFrame([{"발표일": "2023-10-27"}])
        mock_yonhap.return_value = df_yonhap

        # Execute
        result = self.calendar.get_earnings_by_month(2023, 10)

        # Verify
        pd.testing.assert_frame_equal(result, df_yonhap)
        mock_wise.assert_called_once_with(2023, 10)
        mock_fn.assert_called_once_with(2023, 10)
        mock_yonhap.assert_called_once_with(2023, 10)

    @patch('builtins.print')
    @patch.object(NaverEarningsCalendar, '_get_from_yonhap')
    @patch.object(NaverEarningsCalendar, '_get_from_fnguide')
    @patch.object(NaverEarningsCalendar, '_get_from_wisereport')
    def test_get_earnings_by_month_all_fail(self, mock_wise, mock_fn, mock_yonhap, mock_print):
        # Setup
        mock_wise.return_value = pd.DataFrame()
        mock_fn.return_value = pd.DataFrame()
        mock_yonhap.return_value = pd.DataFrame()

        # Execute
        result = self.calendar.get_earnings_by_month(2023, 10)

        # Verify
        self.assertTrue(result.empty)
        mock_wise.assert_called_once_with(2023, 10)
        mock_fn.assert_called_once_with(2023, 10)
        mock_yonhap.assert_called_once_with(2023, 10)
        mock_print.assert_called_once_with("  ℹ️  국내 실적발표: 무료 소스 수집 실패. DART API 키 사용 권장 (무료 발급)")

if __name__ == '__main__':
    unittest.main()

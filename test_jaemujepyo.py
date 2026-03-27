import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import jaemujepyo

class TestGetFinancialSummary(unittest.TestCase):
    def setUp(self):
        # We need to mock jaemujepyo.dart before running tests, since it might be None
        self.patcher = patch('jaemujepyo.dart')
        self.mock_dart = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_happy_path_cfs(self):
        # Create a mock DataFrame representing CFS data
        data = {
            'fs_div': ['CFS', 'CFS', 'OFS'],
            'account_nm': ['매출액', '영업이익', '매출액'],
            'thstrm_amount': ['100,000,000', '50,000,000', '80,000,000'],
            'frmtrm_amount': ['90,000,000', '40,000,000', '70,000,000']
        }
        mock_df = pd.DataFrame(data)
        self.mock_dart.finstate.return_value = mock_df

        result = jaemujepyo.get_financial_summary('005930', 2023)

        self.assertIsNotNone(result)
        # Check that it filtered only CFS
        self.assertEqual(len(result), 2)
        # Check indices are correct
        self.assertListEqual(list(result.index), ['매출액', '영업이익'])
        # Check columns are renamed properly
        self.assertIn('2023년 (억)', result.columns)
        self.assertIn('2022년 (억)', result.columns)
        # Check values are converted and divided by 100,000,000
        self.assertEqual(result.loc['매출액', '2023년 (억)'], 1.0)
        self.assertEqual(result.loc['영업이익', '2022년 (억)'], 0.4)

    def test_fallback_ofs(self):
        # Create a mock DataFrame representing OFS data only (no CFS)
        data = {
            'fs_div': ['OFS', 'OFS'],
            'account_nm': ['매출액', '영업이익'],
            'thstrm_amount': ['80,000,000', '40,000,000'],
            'frmtrm_amount': ['70,000,000', '30,000,000']
        }
        mock_df = pd.DataFrame(data)
        self.mock_dart.finstate.return_value = mock_df

        result = jaemujepyo.get_financial_summary('005930', 2023)

        self.assertIsNotNone(result)
        # Check that it fell back to OFS
        self.assertEqual(len(result), 2)
        self.assertListEqual(list(result.index), ['매출액', '영업이익'])
        self.assertEqual(result.loc['매출액', '2023년 (억)'], 0.8)

    def test_empty_dataframe(self):
        # Mock finstate to return an empty DataFrame
        self.mock_dart.finstate.return_value = pd.DataFrame()

        result = jaemujepyo.get_financial_summary('005930', 2023)

        self.assertIsNone(result)

    def test_none_dataframe(self):
        # Mock finstate to return None
        self.mock_dart.finstate.return_value = None

        result = jaemujepyo.get_financial_summary('005930', 2023)

        self.assertIsNone(result)

    def test_exception_handling(self):
        # Mock finstate to raise an Exception
        self.mock_dart.finstate.side_effect = Exception("API error")

        result = jaemujepyo.get_financial_summary('005930', 2023)

        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()

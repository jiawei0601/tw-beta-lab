import math
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from beta import aligned_returns, regress
from server import calculate


class RegressionTests(unittest.TestCase):
    def test_known_line(self):
        rows = [{'date': '2025-01-02', 'from': '2025-01-01', 'market': x / 100,
                 'stock': .011 + 1.25 * x / 100} for x in range(-10, 11)]
        r = regress(rows)
        self.assertAlmostEqual(r['beta'], 1.25)
        self.assertAlmostEqual(r['intercept'], .011)
        self.assertAlmostEqual(r['r2'], 1)
        self.assertAlmostEqual(r['beta_se'], 0)

    def test_rf_changes_intercept_not_beta(self):
        rows = [{'date': '2025-01-02', 'from': '2025-01-01', 'market': x / 100,
                 'stock': .011 + 1.25 * x / 100} for x in range(-10, 11)]
        r = regress(rows, .02, 'monthly')
        self.assertAlmostEqual(r['beta'], 1.25)
        self.assertAlmostEqual(r['intercept'], .011 + .25 * ((1.02 ** (1/12))-1))

    def test_flat_and_insufficient(self):
        with self.assertRaises(ValueError):
            regress([])
        with self.assertRaises(ValueError):
            regress([{'market': 0, 'stock': 0}] * 20)

    def test_flat_stock_has_zero_explanatory_power(self):
        rows = [{'date': '2025-01-02', 'from': '2025-01-01', 'market': x/100, 'stock': 0} for x in range(20)]
        self.assertEqual(regress(rows)['r2'], 0)


class AlignmentTests(unittest.TestCase):
    def align(self, s, m, start='2025-01-01', end='2025-06-30', f='daily'):
        return aligned_returns(s, m, date.fromisoformat(start), date.fromisoformat(end), f, date(2025, 7, 10))[0]

    def test_daily_missing_price_does_not_bridge(self):
        s = {'2025-01-02':100, '2025-01-06':110, '2025-01-07':121}
        m = {'2025-01-02':100, '2025-01-03':105, '2025-01-06':110, '2025-01-07':121}
        rows = self.align(s,m)
        self.assertEqual([r['date'] for r in rows], ['2025-01-07'])
        self.assertAlmostEqual(rows[0]['stock'], .1)

    def test_start_excludes_return_from_before_window(self):
        s = {'2024-12-31':100, '2025-01-02':110, '2025-01-03':121}
        self.assertEqual(len(self.align(s,s)), 1)

    def test_mismatched_month_end_excluded(self):
        s={'2025-01-31':100,'2025-02-27':110,'2025-03-31':120}
        m={'2025-01-31':100,'2025-02-28':110,'2025-03-31':120}
        self.assertEqual(self.align(s,m,f='monthly'), [])

    def test_missing_month_not_single_month_return(self):
        s={'2025-01-31':100,'2025-03-31':120,'2025-04-30':126}
        rows=self.align(s,s,f='monthly')
        self.assertEqual([r['date'] for r in rows], ['2025-04-30'])

    def test_week_year_boundary(self):
        s={'2024-12-27':100,'2025-01-03':110,'2025-01-10':121}
        rows=self.align(s,s,start='2024-12-01',f='weekly')
        self.assertEqual(len(rows),2)

    def test_partial_historical_month(self):
        s={'2025-01-31':100,'2025-02-28':110,'2025-03-14':121}
        rows=self.align(s,s,end='2025-03-14',f='monthly')
        self.assertEqual([r['date'] for r in rows],['2025-02-28'])

    def test_partial_historical_week(self):
        s={'2025-01-03':100,'2025-01-08':110}
        self.assertEqual(self.align(s,s,end='2025-01-08',f='weekly'),[])

    def test_current_day_and_period_excluded(self):
        s={'2025-06-30':100,'2025-07-09':110,'2025-07-10':121}
        rows=self.align(s,s,end='2025-07-10')
        self.assertNotIn('2025-07-10',[r['date'] for r in rows])
        self.assertEqual(self.align(s,s,end='2025-07-10',f='monthly'),[])


class ApiTests(unittest.TestCase):
    def test_validate_before_fetch(self):
        for change in [{'codes':'../../etc'}, {'codes':'2330','rf':'NaN'}, {'codes':'2330','mode':'x'}, {'codes':'2330','frequency':'x'}]:
            with self.subTest(change=change),patch('server.fetch') as fetch:
                with self.assertRaises(ValueError):
                    calculate(dict({'start':'2025-01-01','end':'2025-03-01'},**change))
                fetch.assert_not_called()

    def test_partial_failure_and_otc_resolution(self):
        series={(date(2025,1,1)+timedelta(days=i)).isoformat():100+i*i for i in range(35)}
        def mock_fetch(symbol,*args):
            if symbol in ('6488.TW','9999.TW','9999.TWO'):
                raise ValueError(f'查無 {symbol}')
            return {'series':series,'name':symbol,'symbol':symbol,'fetched_at':'test'}
        with patch('server.fetch',side_effect=mock_fetch):
            result=calculate({'codes':'6488 9999','start':'2025-01-01','end':'2025-02-05'})
        self.assertEqual(result['results'][0]['symbol'],'6488.TWO')
        self.assertAlmostEqual(result['results'][0]['beta'],1)
        self.assertIn('error',result['results'][1])


if __name__ == '__main__':
    unittest.main()

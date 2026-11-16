import unittest
from unittest.mock import patch

import psycopg2
import app as inventory


class DashboardTests(unittest.TestCase):
    def test_collections_and_missing_values(self):
        products = [dict(id=7, sku_number='A-7', name='<Widget>',
                         stock=[dict(date=None, quantity=0), dict(date='2026-01-01', quantity=10)],
                         orders=[dict(order_date='2026-02-01', supply_date=None, quantity=123),
                                 dict(order_date='2026-03-01', supply_date=None, quantity=456)],
                         sales=[dict(id=9, receipt=0)]),
                    dict(id=8, sku_number='B-8', name=None, stock=[], orders=[], sales=[])]
        with patch.object(inventory, 'get_inventory', return_value=(products, dict(stock=1, orders=0, sales=0))):
            response = inventory.app.test_client().get('/')
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count('<td>123</td>'), 1)
        self.assertEqual(html.count('<td>456</td>'), 1)
        self.assertIn('&lt;Widget&gt;', html)
        self.assertIn('No stock records', html)
        self.assertIn('Unassigned legacy records', html)

    def test_database_error_is_generic(self):
        with patch.object(inventory, 'get_inventory', side_effect=psycopg2.OperationalError('secret')):
            response = inventory.app.test_client().get('/')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', response.get_data(as_text=True))

    def test_connection_closed_and_records_grouped(self):
        from unittest.mock import MagicMock
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchall.side_effect = [
            [dict(id=7, sku_number='A', name='First'), dict(id=8, sku_number='B', name='Second')],
            [dict(id=99, product_id=8, quantity=3)],
            [dict(id=7, product_id=7), dict(id=8, product_id=7)], []]
        cur.fetchone.return_value = dict(stock=0, orders=0, sales=0)
        with patch.object(inventory.psycopg2, 'connect', return_value=conn):
            products, _ = inventory.get_inventory()
        self.assertEqual(products[0]['stock'], [])
        self.assertEqual(products[1]['stock'][0]['id'], 99)
        self.assertEqual(len(products[0]['orders']), 2)
        conn.close.assert_called_once()
        cur.execute.side_effect = psycopg2.OperationalError()
        conn.close.reset_mock()
        with patch.object(inventory.psycopg2, 'connect', return_value=conn):
            with self.assertRaises(psycopg2.Error):
                inventory.get_inventory()
        conn.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()

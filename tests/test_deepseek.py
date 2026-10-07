import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('balance', Path(__file__).parents[1] / 'deepseek/update-deepseek.py')
balance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(balance)

class BalanceTests(unittest.TestCase):
    def test_currency_and_compact_amounts(self):
        self.assertEqual(balance.amount({'currency': 'CNY', 'total_balance': '110'}), '¥110.00')
        self.assertEqual(balance.amount({'currency': 'USD', 'total_balance': '2000000'}, True), '$2.00M')

    def test_balance_only_and_failure_preserves_previous_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.json'
            config.write_text(json.dumps({'api_key': 'test-placeholder'}))
            output = root / 'deepseek.json'
            with patch.object(balance, 'ROOT', root), patch.object(balance, 'CONFIG', config), patch.object(balance, 'OUTPUT', output):
                reply = io.BytesIO(json.dumps({'balance_infos': [{'currency': 'CNY', 'total_balance': '100'}]}).encode())
                with patch.object(balance.urllib.request, 'urlopen', return_value=reply):
                    balance.refresh()
                data = json.loads(output.read_text())
                self.assertEqual(data['metrics'], [{'title': 'Total balance', 'formattedValue': '¥100.00'}])
                self.assertEqual(data['metricsBarValue'], '¥100.00')
                with patch.object(balance.urllib.request, 'urlopen', side_effect=OSError('offline')):
                    balance.refresh()
                failed = json.loads(output.read_text())
                self.assertEqual(failed['metrics'][0], data['metrics'][0])
                self.assertEqual(failed['metrics'][1]['title'], 'Balance status')

if __name__ == '__main__':
    unittest.main()

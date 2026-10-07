#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Adapted for runcat-ai-metrics from RunCat Neo integration examples.
# Modifications: usage aggregation, countdowns, and DeepSeek balance integration.
"""RunCat DeepSeek total-balance producer."""
import fcntl
import json
import os
import tempfile
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path.home() / '.runcat/deepseek'
CONFIG = ROOT / 'config.json'
OUTPUT = ROOT / 'deepseek.json'


def amount(balance, compact=False):
    value = Decimal(balance['total_balance'])
    if not value.is_finite() or value < 0:
        raise ValueError('Invalid balance')
    currency = balance['currency']
    prefix = {'CNY': '¥', 'USD': '$'}.get(currency, currency + ' ')
    if compact:
        for scale, suffix in ((10**9, 'B'), (10**6, 'M'), (10**3, 'K')):
            if value >= scale:
                return f'{prefix}{value / scale:.2f}{suffix}'
    return f'{prefix}{value:.2f}'


def save(snapshot):
    fd, name = tempfile.mkstemp(dir=ROOT, prefix='.deepseek-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(snapshot, stream, ensure_ascii=False)
        os.replace(name, OUTPUT)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def refresh():
    now = datetime.now(timezone.utc)
    rows = []
    snapshot = {'title': 'DeepSeek', 'symbol': 'creditcard', 'metrics': rows,
                'lastUpdatedDate': now.strftime('%Y-%m-%dT%H:%M:%SZ')}
    config = json.loads(CONFIG.read_text())
    key = config.get('api_key', '').strip()
    if not key or key == 'PASTE_YOUR_DEEPSEEK_API_KEY_HERE':
        rows.append({'title': 'Total balance', 'formattedValue': 'API key not configured'})
    else:
        try:
            request = urllib.request.Request('https://api.deepseek.com/user/balance',
                headers={'Authorization': 'Bearer ' + key, 'Accept': 'application/json'})
            with urllib.request.urlopen(request, timeout=20) as result:
                data = json.load(result)
            balances = data['balance_infos']
            if not balances:
                raise ValueError('No balances returned')
            text = ' / '.join(amount(b) for b in balances)
            rows.append({'title': 'Total balance', 'formattedValue': text})
            snapshot['metricsBarValue'] = ' / '.join(amount(b, compact=True) for b in balances)
        except Exception:
            # Never log credentials or server response bodies.
            previous = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
            old = next((r for r in previous.get('metrics', []) if r['title'] == 'Total balance'), None)
            rows.append(old or {'title': 'Total balance', 'formattedValue': 'Unavailable'})
            rows.append({'title': 'Balance status', 'formattedValue': 'Refresh failed; previous value if available'})
    save(snapshot)


def main():
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (ROOT / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        refresh()


if __name__ == '__main__':
    main()

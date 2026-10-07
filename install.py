#!/usr/bin/env python3
"""Install or uninstall per-user macOS integrations; keep credentials on uninstall."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

SOURCE = Path(__file__).resolve().parent


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.runcat-')
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    os.replace(temp, path)


def merge_hook(data, script, uninstall=False):
    entries = data.setdefault('hooks', {}).setdefault('Stop', [])
    retained = []
    for entry in entries:
        hooks = []
        for hook in entry.get('hooks', []):
            try:
                ours = str(script) in shlex.split(hook.get('command', ''))
            except ValueError:
                ours = False
            if not ours:
                hooks.append(hook)
        if hooks:
            retained.append({**entry, 'hooks': hooks})
    if not uninstall:
        command = shlex.join([sys.executable, str(script)])
        retained.append({'hooks': [{'type': 'command', 'command': command, 'timeout': 120}]})
    data['hooks']['Stop'] = retained
    return data


def timer(label, script, interval, args=(), uninstall=False):
    path = Path.home() / 'Library/LaunchAgents' / (label + '.plist')
    domain = f'gui/{os.getuid()}'
    subprocess.run(['launchctl', 'bootout', domain + '/' + label], capture_output=True)
    if uninstall:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps({
        'Label': label, 'ProgramArguments': [sys.executable, str(script), *args],
        'StartInterval': interval, 'RunAtLoad': True, 'ProcessType': 'Background',
        'StandardErrorPath': str(script.parent / (label + '.log')),
    }))
    subprocess.run(['launchctl', 'bootstrap', domain, str(path)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('integration', choices=['codex', 'deepseek', 'all'])
    parser.add_argument('--uninstall', action='store_true')
    options = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('Installation requires macOS.')
    if options.integration in ('codex', 'all'):
        root = Path.home() / '.codex'
        script = root / 'runcat-hook.py'
        root.mkdir(parents=True, exist_ok=True)
        if not options.uninstall:
            subprocess.run(['npm', 'install', '--prefix', str(root / 'runcat-tools'),
                            'ccusage@20.0.26'], check=True)
            shutil.copy2(SOURCE / 'codex/runcat-hook.py', script)
        hooks = root / 'hooks.json'
        data = json.loads(hooks.read_text()) if hooks.exists() else {}
        if hooks.exists():
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            shutil.copy2(hooks, hooks.with_name('hooks.json.backup-' + stamp))
        write_json(hooks, merge_hook(data, script, options.uninstall))
        timer('dev.runcat.codex-countdown', script, 60, ['--refresh-countdown'], options.uninstall)
        print('Codex: restart Codex and trust the hook if prompted. Source:', root / 'runcat-usage.json')
    if options.integration in ('deepseek', 'all'):
        root = Path.home() / '.runcat/deepseek'
        script = root / 'update-deepseek.py'
        if not options.uninstall:
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            config = root / 'config.json'
            if not config.exists():
                write_json(config, {'api_key': ''})
            config.chmod(0o600)
            shutil.copy2(SOURCE / 'deepseek/update-deepseek.py', script)
            subprocess.run([sys.executable, str(script)], check=True)
            print('Set your API key locally in:', config)
            print('RunCat source:', root / 'deepseek.json')
        timer('dev.runcat.deepseek', script, 3600, uninstall=options.uninstall)
    if options.uninstall:
        print('Hooks/timers removed. Installed files, credentials and snapshots retained.')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Install the lightweight per-user RunCat countdown refresh timer on macOS."""

import os
import plistlib
import subprocess
import sys
from pathlib import Path


def main():
    home = Path.home()
    script = home / ".codex/runcat-hook.py"
    if not script.is_file():
        raise SystemExit("Copy runcat-hook.py to ~/.codex first.")
    label = "dev.runcat.codex-countdown"
    target = home / "Library/LaunchAgents" / f"{label}.plist"
    target.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "Label": label,
        "ProgramArguments": [sys.executable, str(script), "--refresh-countdown"],
        "StartInterval": 60,
        "RunAtLoad": True,
        "ProcessType": "Background",
        "StandardErrorPath": str(home / ".codex/runcat-countdown.log"),
    }
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{label}"], capture_output=True)
    target.write_bytes(plistlib.dumps(config))
    subprocess.run(["launchctl", "bootstrap", domain, str(target)], check=True)
    print(f"Countdown refresh enabled every 60 seconds: {target}")


if __name__ == "__main__":
    main()

# Codex Integration Sample

A small Python script that lets RunCat Neo's Custom Metrics card show the account rate limits, reset countdowns, and local token totals. Codex runs the script after each turn through a `Stop` lifecycle hook. The script reads the latest token-count event from the session transcript and writes a Custom Metrics JSON snapshot to `~/.codex/runcat-usage.json`.

This sample uses Codex's local session transcript, whose format may change between Codex releases. If it stops working after an update, inspect the latest `token_count` event under `~/.codex/sessions/` and adjust the parser in `runcat-hook.py`.

## Setup

1. Install Python 3.9+ and Node.js/npm, then install the tested ccusage version locally:
   ```bash
   npm install --prefix ~/.codex/runcat-tools ccusage@20.0.26
   ```
   The hook runs this installed binary, never `npx` or a package download. It uses
   offline, no-cost reports. Logs stay local. See [ccusage](https://github.com/ccusage/ccusage).

   Copy the script from this sample directory and make it executable:
   ```bash
   cp runcat-hook.py ~/.codex/runcat-hook.py
   chmod +x ~/.codex/runcat-hook.py
   ```
2. Register it in `~/.codex/hooks.json`:
   ```json
   {
     "hooks": {
       "Stop": [
         {
           "hooks": [
             {
               "type": "command",
               "command": "/Users/YOU/.codex/runcat-hook.py",
               "timeout": 120
             }
           ]
         }
       ]
     }
   }
   ```
   Replace `/Users/YOU` with your home path. If you already have `~/.codex/hooks.json`, add the inner entry to its existing `Stop` array instead of replacing the file.
3. Restart Codex, then use `/hooks` to review and trust the new hook if prompted.
4. Complete a turn in Codex. The script creates `~/.codex/runcat-usage.json` after the turn finishes.
5. In RunCat Neo, open **Settings → Metrics → Custom Metrics**, click **Add Custom Metrics Source**, and choose `~/.codex/runcat-usage.json`.
6. Optional: click the Metrics Bar and flip the source's toggle to show today’s token total directly in the menu bar.

The hook feature is enabled by default in current Codex releases. If `/hooks` is unavailable, add this to `~/.codex/config.toml` and restart Codex:

```toml
[features]
hooks = true
```

## What it displays

- **5h**, **7d**, or another available quota window: used percentage and a progress bar.
- **5h reset**, **7d reset**, etc.: remaining days/hours/minutes and a time-remaining bar.
- **Today tokens**: local-log usage since midnight.
- **7d tokens** / **30d tokens**: rolling totals displayed as numbers only.
- **30d daily average**: 30-day total divided by 30, including zero-use days and today's partial day.

Model and context rows are deliberately omitted. The menu bar shows today's tokens in K/M/B. All token rows use decimal units: K = 1,000, M = 1,000,000, B = 1,000,000,000; at most two decimal places.
Token rows deliberately have no charts or progress bars. Quota usage and reset
countdowns use the existing Custom Metrics progress bars; the released app needs
no rebuilding.

The default timezone is `Asia/Shanghai`. ccusage handles event deltas, replayed
history and supported compaction records. Use its `totalTokens` directly: do not
add cache or reasoning counts again. These are retained **local-log** totals,
not account-wide billing or quota consumption. Missing/deleted logs mean incomplete
history; this is not evidence of zero usage.

Each hook refresh queries 30 days once (90-second subprocess limit; 120-second
hook timeout). A file lock skips overlapping refreshes, and output is replaced
atomically. If statistics fail, quota still updates and a visible
`Token statistics: Unavailable` row appears instead of false zero totals.
Sessions without account rate limits preserve previous quota/reset rows and label
them as not refreshed. Parsing failures do not interrupt Codex.

## Automatic countdown refresh

Run the following after copying the hook to `~/.codex/runcat-hook.py`:

```bash
python3 install-countdown.py
```

This installs a per-user launchd agent, `dev.runcat.codex-countdown`, that invokes
`runcat-hook.py --refresh-countdown` every 60 seconds while logged in. The lightweight
refresh only updates clocks in the existing JSON; it does not invoke ccusage,
scan transcripts, or change the usage timestamp. After expiry it shows
`Due — awaiting quota refresh`, without inventing a new reset time or zero usage.
Token totals and quota percentages continue to refresh after Codex turns.

To remove the countdown timer:

```bash
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/dev.runcat.codex-countdown.plist
rm ~/Library/LaunchAgents/dev.runcat.codex-countdown.plist
```

## Customizing the output

The output JSON shape is documented in [`https://github.com/runcat-dev/RunCatNeo/blob/main/docs/CustomMetricsSchema.md`](https://github.com/runcat-dev/RunCatNeo/blob/main/docs/CustomMetricsSchema.md). Edit the `snapshot` dictionary to add rows, change the card title, or pick a different SF Symbol.

- `RUNCAT_OUT_FILE`: output path (default `~/.codex/runcat-usage.json`).
- `RUNCAT_TIMEZONE`: IANA timezone (default `Asia/Shanghai`).
- `RUNCAT_CCUSAGE`: executable path; defaults to the installation above, then `ccusage` on PATH.
- `CODEX_HOME`: honored by ccusage for log discovery.

Token totals refresh after a turn; dates/totals remain at the last refresh while
Codex is idle. The countdown timer updates independently each minute.
If your hook environment cannot find Python, use its absolute path followed by
the script path in the hook command.

Run regression tests with `python3 -m unittest discover -s codex -p 'test_*.py'`.

## Troubleshooting

- File never appears → run the script manually with a recent session transcript:
  ```bash
  transcript="$(find ~/.codex/sessions -name '*.jsonl' -type f -print0 \
    | xargs -0 stat -f '%m %N' \
    | sort -nr \
    | head -n 1 \
    | cut -d ' ' -f 2-)"
  printf '{"model":"Codex","transcript_path":"%s"}\n' "$transcript" \
    | ~/.codex/runcat-hook.py
  python3 -m json.tool ~/.codex/runcat-usage.json
  ```
- Quota is missing → check that `transcript_path` exists and contains a recognized `token_count` event. API-key sessions may not include account quotas.
- **Token statistics: Unavailable** → verify the installed ccusage binary works with `codex daily --last 30 --timezone Asia/Shanghai --json --offline --no-cost`; check stderr for timeouts or parser errors.
- The hook does not run → open `/hooks` in Codex and confirm the hook is enabled and trusted.
- The card footer shows **Last updated: Failed** in red → confirm `~/.codex/runcat-usage.json` still exists and is readable, then complete another Codex turn.

# DeepSeek total balance

Like the Bitcoin sample, this producer queries an API and writes a Custom Metrics
JSON file. The card displays **Total balance** with a currency symbol and two
decimal places; the Metrics Bar displays the amount, using K/M/B for large values.
There are no token rows or percentage bars: an account balance has no fixed maximum.

The official `https://api.deepseek.com/user/balance` endpoint supplies
`total_balance` (grant plus topped-up balance). Different currencies are displayed
separately, never added together. No model-generation requests are made.

Installed paths:

- `~/.runcat/deepseek/config.json`: set `api_key`; owner-only permissions.
- `~/.runcat/deepseek/update-deepseek.py`: installed copy of this script.
- `~/.runcat/deepseek/deepseek.json`: add to RunCat Custom Metrics.
- `~/Library/LaunchAgents/dev.runcat.deepseek.plist`: refresh at login and every hour.

Enable this source in the Metrics Bar to show its amount in the menu bar.
The key stays outside the repository. After filling it in, wait for the hourly
refresh or run the installed script once. Missing configuration is shown explicitly;
failed fetches retain the previous balance with a failure label.

To stop the timer:

```sh
launchctl bootout gui/$(id -u)/dev.runcat.deepseek
```

# project-tracker

Scans local git repos, grabs each one's last commit info, and syncs it to a
Google Sheet. The Sheet is the dashboard — there's no separate UI.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create a Google Cloud project and OAuth client:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a project (or reuse one) and enable the **Google Sheets API**.
   - Under "APIs & Services" → "Credentials", create an **OAuth client ID**
     of type "Desktop app".
   - Download the JSON and save it as `credentials.json` in this folder.
     This file is gitignored — never commit it.

3. Create a Google Sheet and copy its ID from the URL
   (`https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`). Share it with
   the Google account you'll authenticate as, if needed.

4. Copy the config template and fill in your details:
   ```
   cp config.yaml.example config.yaml
   ```
   Edit `config.yaml` with your `sheet_id` and the list of project paths to
   track. `config.yaml` is gitignored since it contains local paths and
   possibly a computer name — keep your real one out of version control.

## Running it

```
python tracker.py
```

On the first run, a browser window opens for Google OAuth consent. A
`token.json` is cached afterward (also gitignored) and silently refreshed on
later runs.

The script prints a summary of rows updated/added/skipped, and exits
non-zero if the Sheets API call fails.

## Scheduling (optional)

The script itself doesn't schedule anything — run it manually, or wire it up
with your OS scheduler if you want it to run automatically.

**Windows (Task Scheduler):**
1. Open Task Scheduler → "Create Basic Task".
2. Trigger: e.g. "Daily" repeating every hour, or "At log on".
3. Action: "Start a program"
   - Program/script: path to your `python.exe`
   - Arguments: `tracker.py`
   - Start in: this project's folder (so `config.yaml` etc. are found)

**macOS/Linux (cron):** run every hour:
```
0 * * * * cd /path/to/project-tracker && /usr/bin/python3 tracker.py >> tracker.log 2>&1
```

## Notes

- `credentials.json`, `token.json`, and `config.yaml` are all gitignored —
  they either hold secrets or personal/local details (file paths, computer
  name). Only `config.yaml.example` is committed.

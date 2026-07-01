# Project Tracker → Google Sheets

## Goal
Script that scans a list of local git repos, pulls the last commit info from each, and syncs it to a Google Sheet. No separate UI — the Sheet is the dashboard.

## Tech
- Python 3
- `google-api-python-client`, `google-auth-oauthlib`, `google-auth`
- `subprocess` for git (no GitPython dep needed)

## Config file (`config.yaml`)
```yaml
sheet_id: "<google sheet id>"
computer_name: "my-desktop"  # optional override, else use hostname
projects:
  - path: "C:/path/to/project-one"
    description: "Internal tool for X"
  - path: "C:/path/to/project-two"
    description: "Client Y website"
```

## Sheet schema (columns, row 1 = header)
| Project Name | Description | Path | Computer | Last Commit Msg | Last Commit Date | Last Synced |

- Project Name = folder name (basename of path)
- Row key = Project Name + Computer (composite) — allows same project on multiple machines as separate rows

## Script logic
1. Load `config.yaml`
2. For each project:
   - Run `git -C <path> log -1 --pretty=format:%s|%cI` → split into message + ISO date
   - If not a git repo or no commits, log a warning and skip
3. Get computer name: `config.computer_name` if set, else `socket.gethostname()`
4. Auth to Sheets API via OAuth (see below)
5. Read existing sheet rows, build a dict keyed by (Project Name, Computer)
6. For each scanned project: if key exists → update that row's Description/Path/Last Commit Msg/Last Commit Date/Last Synced; if not → append new row
7. Write changes back with a single batchUpdate call (not one call per row)
8. Print summary to stdout (rows updated / added / skipped)

## Auth (OAuth)
- Standard installed-app flow: `credentials.json` (user provides, from Google Cloud Console) + cached `token.json`
- On first run, opens browser for consent; subsequent runs reuse cached token, refresh silently if expired
- Scope: `https://www.googleapis.com/auth/spreadsheets`

## File structure
```
project-tracker/
  config.yaml
  credentials.json      # gitignored
  token.json            # gitignored, auto-generated
  tracker.py
  requirements.txt
```

## Running it
- Manual: `python tracker.py`
- Suggest (not build) a cron entry / Windows Task Scheduler entry to run it e.g. every hour or on login — leave instructions in README, don't over-engineer scheduling into the script itself

## Error handling
- Missing path in config → warn, skip, continue
- Path exists but not a git repo → warn, skip, continue
- Sheets API failure → print error, exit non-zero
- Don't crash the whole run because one project fails

## Explicitly out of scope (don't build)
- No GUI/web dashboard
- No git commit hooks
- No database — Sheet is the only store
- No multi-user auth handling beyond single OAuth user

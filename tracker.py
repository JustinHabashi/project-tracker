"""Scan local git repos and sync their latest commit info to a Google Sheet."""

import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"
CREDENTIALS_PATH = SCRIPT_DIR / "credentials.json"
TOKEN_PATH = SCRIPT_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADER = [
    "Project Name",
    "Description",
    "Path",
    "Computer",
    "Last Commit Msg",
    "Last Commit Date",
    "Last Synced",
]


def load_config():
    if not CONFIG_PATH.exists():
        print(f"ERROR: config file not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_computer_name(config):
    return config.get("computer_name") or socket.gethostname()


def get_last_commit(path):
    """Return (message, iso_date) for the last commit, or None if unavailable."""
    if not Path(path).is_dir():
        print(f"WARNING: path does not exist, skipping: {path}")
        return None

    result = subprocess.run(
        ["git", "-C", str(path), "log", "-1", "--pretty=format:%s|%cI"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"WARNING: not a git repo, skipping: {path}")
        return None

    output = result.stdout.strip()
    if not output:
        print(f"WARNING: no commits found, skipping: {path}")
        return None

    message, _, date = output.rpartition("|")
    if not message:
        print(f"WARNING: unexpected git log output, skipping: {path}")
        return None

    return message, date


def scan_projects(projects):
    """Return list of dicts with project name/description/path/commit info."""
    scanned = []
    skipped = 0
    for project in projects:
        path = project.get("path")
        description = project.get("description", "")
        if not path:
            print(f"WARNING: project entry missing 'path', skipping: {project}")
            skipped += 1
            continue

        try:
            commit = get_last_commit(path)
        except Exception as exc:
            print(f"WARNING: error reading git info for {path}: {exc}")
            skipped += 1
            continue

        if commit is None:
            skipped += 1
            continue

        message, date = commit
        scanned.append(
            {
                "name": Path(path).name,
                "description": description,
                "path": path,
                "last_commit_msg": message,
                "last_commit_date": date,
            }
        )

    return scanned, skipped


def authenticate():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(
                    f"ERROR: {CREDENTIALS_PATH} not found. Download OAuth client "
                    "credentials from Google Cloud Console and save them there.",
                    file=sys.stderr,
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds


def read_existing_rows(service, sheet_id, sheet_name):
    range_ = f"{sheet_name}!A:G"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=range_)
        .execute()
    )
    values = result.get("values", [])

    if not values:
        # Sheet is empty; write the header row now.
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": [HEADER]},
        ).execute()
        return {}

    existing = {}
    for i, row in enumerate(values[1:], start=2):  # row 1 is header
        row = row + [""] * (len(HEADER) - len(row))  # pad short rows
        key = (row[0], row[3])  # Project Name, Computer
        existing[key] = i

    return existing


def sync_to_sheet(service, sheet_id, sheet_name, scanned, computer_name):
    existing = read_existing_rows(service, sheet_id, sheet_name)
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    data = []
    updated = 0
    added = 0
    next_row = max(existing.values(), default=1) + 1

    for project in scanned:
        key = (project["name"], computer_name)
        row_values = [
            project["name"],
            project["description"],
            project["path"],
            computer_name,
            project["last_commit_msg"],
            project["last_commit_date"],
            now,
        ]

        if key in existing:
            row_num = existing[key]
            updated += 1
        else:
            row_num = next_row
            next_row += 1
            added += 1

        data.append(
            {"range": f"{sheet_name}!A{row_num}:G{row_num}", "values": [row_values]}
        )

    if data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": data},
        ).execute()

    return updated, added


def main():
    config = load_config()
    computer_name = get_computer_name(config)
    sheet_id = config.get("sheet_id")
    sheet_name = config.get("sheet_name", "Sheet1")

    if not sheet_id:
        print("ERROR: 'sheet_id' missing from config.yaml", file=sys.stderr)
        sys.exit(1)

    projects = config.get("projects", [])
    scanned, skipped = scan_projects(projects)

    try:
        creds = authenticate()
        service = build("sheets", "v4", credentials=creds)
        updated, added = sync_to_sheet(
            service, sheet_id, sheet_name, scanned, computer_name
        )
    except HttpError as exc:
        print(f"ERROR: Google Sheets API failure: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Sync complete: {updated} row(s) updated, {added} row(s) added, "
        f"{skipped} project(s) skipped."
    )


if __name__ == "__main__":
    main()

import requests
import json
import os
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("JIRA_BASE_URL")
EMAIL    = os.getenv("JIRA_EMAIL")
TOKEN    = os.getenv("JIRA_API_TOKEN")
PROJECT  = os.getenv("JIRA_PROJECT_KEY")

auth    = HTTPBasicAuth(EMAIL, TOKEN)
headers = {"Accept": "application/json"}

def fetch_and_save():
    url = f"{BASE_URL}/rest/api/3/search/jql"
    params = {
        "jql": f"project={PROJECT} ORDER BY priority DESC",
        "fields": "summary,status,priority,assignee,description,duedate,labels,created,updated",
        "maxResults": 50
    }
    response = requests.get(url, headers=headers, auth=auth, params=params)
    print(f"Status code: {response.status_code}")
    print(f"Response preview: {response.text[:500]}")
    response.raise_for_status()
    issues = response.json()["issues"]

    # Convert to TaskPilot format
    board = {
        "board": {
            "project": PROJECT,
            "sprint": "SCRUM Sprint 0",
            "generated_at": "2026-06-20T08:00:00Z"
        },
        "issues": []
    }

    for issue in issues:
        f = issue["fields"]
        priority = (f.get("priority") or {}).get("name", "P3")
        priority_map = {
            "Highest": "P1", "High": "P2",
            "Medium": "P3", "Low": "P4", "Lowest": "P4"
        }
        board["issues"].append({
            "id": issue["key"],
            "title": f.get("summary", ""),
            "description": str(f.get("description", "") or ""),
            "status": f.get("status", {}).get("name", "open").lower(),
            "severity": priority_map.get(priority, "P3"),
            "assignee": f.get("assignee", {}).get("displayName", "") if f.get("assignee") else "",
            "reporter": "",
            "team": "qa",
            "created_at": f.get("created", ""),
            "updated_at": f.get("updated", ""),
            "deadline": f.get("duedate", "") or "",
            "labels": [l for l in (f.get("labels") or [])],
            "blocks": [],
            "blocked_by": [],
            "sprint": "SCRUM Sprint 0",
            "story_points": 3,
            "business_impact": ""
        })

    with open("data/raw/my_jira_board.json", "w") as out:
        json.dump(board, out, indent=2)

    print(f"[OK] Fetched {len(issues)} issues from Jira!")
    print("Saved to data/raw/my_jira_board.json")

if __name__ == "__main__":
    fetch_and_save()
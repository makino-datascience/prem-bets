"""Fetch the current Premier League table from football-data.org and save it as standings.json.

Runs inside GitHub Actions. The API key comes from the FOOTBALL_DATA_KEY repository secret,
so it never appears in the website's code.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

URL = "https://api.football-data.org/v4/competitions/PL/standings"
OUT = os.path.join(os.path.dirname(__file__), "..", "standings.json")


def main():
    key = os.environ.get("FOOTBALL_DATA_KEY", "").strip()
    if not key:
        sys.exit("FOOTBALL_DATA_KEY secret is missing. Add it under Settings > Secrets and variables > Actions.")

    req = urllib.request.Request(URL, headers={"X-Auth-Token": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"football-data.org returned {e.code}: {e.read()[:300]!r}")

    total = next(s for s in data["standings"] if s.get("type") == "TOTAL")
    teams = []
    for row in sorted(total["table"], key=lambda r: r["position"]):
        t = row["team"]
        teams.append({
            "name": t.get("name"),
            "shortName": t.get("shortName") or t.get("name"),
            "tla": t.get("tla"),
            "crest": t.get("crest"),
            "p": row.get("playedGames"),
            "w": row.get("won"),
            "d": row.get("draw"),
            "l": row.get("lost"),
            "gf": row.get("goalsFor"),
            "ga": row.get("goalsAgainst"),
            "gd": row.get("goalDifference"),
            "pts": row.get("points"),
        })

    try:
        with open(OUT) as f:
            old = json.load(f)
    except (FileNotFoundError, ValueError):
        old = {}

    if old.get("teams") == teams:
        print("Table unchanged.")
        return

    out = {
        "updatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "season": (data.get("season") or {}).get("startDate", "")[:4],
        "teams": teams,
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"Saved table: {teams[0]['shortName']} top, {teams[-1]['shortName']} bottom.")


if __name__ == "__main__":
    main()

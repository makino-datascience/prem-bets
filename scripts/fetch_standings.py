"""Fetch the Premier League table (football-data.org) and team card counts (ESPN), save as standings.json.

Runs inside GitHub Actions every 30 minutes. The table is checked every run; card counts are
checked about once a day. If ESPN can't be read, the last known card counts are kept and the
table still updates.
"""
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

TABLE_URL = "https://api.football-data.org/v4/competitions/PL/standings"
ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams"
ESPN_STATS_URL = "https://sports.core.api.espn.com/v2/sports/soccer/leagues/eng.1/seasons/{season}/types/1/teams/{team_id}/statistics"
OUT = os.path.join(os.path.dirname(__file__), "..", "standings.json")
CARDS_EVERY_HOURS = 20
UA = {"User-Agent": "Mozilla/5.0 (prem-bets standings job)", "Accept": "application/json"}


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def norm(name):
    s = (name or "").lower().replace("&", "and")
    s = re.sub(r"\b(a?fc)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def get_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def find_stat(obj, wanted):
    """Search ESPN's statistics response for a stat by name, wherever it sits."""
    if isinstance(obj, dict):
        if obj.get("name") == wanted and isinstance(obj.get("value"), (int, float)):
            return obj["value"]
        for v in obj.values():
            r = find_stat(v, wanted)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_stat(v, wanted)
            if r is not None:
                return r
    return None


def match_team(espn_names, teams):
    """Find which football-data team an ESPN team is, by name."""
    keys = [norm(n) for n in espn_names if n]
    for t in teams:
        tn, ts = norm(t["name"]), norm(t["shortName"])
        if any(k and (k == tn or k == ts) for k in keys):
            return t
    for t in teams:
        tn = norm(t["name"])
        if any(k and len(k) > 4 and (k in tn or tn in k) for k in keys):
            return t
    return None


def fetch_cards(teams, season):
    """Return {football-data team name: (yellows, reds)} from ESPN."""
    data = get_json(ESPN_TEAMS_URL, UA)
    espn_teams = [x["team"] for x in data["sports"][0]["leagues"][0]["teams"]]
    result = {}
    for et in espn_teams:
        t = match_team([et.get("displayName"), et.get("shortDisplayName"), et.get("name"), et.get("location")], teams)
        if not t:
            print(f"Cards: couldn't match ESPN team {et.get('displayName')!r}")
            continue
        try:
            stats = get_json(ESPN_STATS_URL.format(season=season, team_id=et["id"]), UA)
        except urllib.error.HTTPError as e:
            print(f"Cards: ESPN returned {e.code} for {et.get('displayName')}")
            continue
        yc, rc = find_stat(stats, "yellowCards"), find_stat(stats, "redCards")
        if yc is None and rc is None:
            print(f"Cards: no card stats found for {et.get('displayName')}")
            continue
        result[t["name"]] = (int(yc or 0), int(rc or 0))
    return result


def main():
    key = os.environ.get("FOOTBALL_DATA_KEY", "").strip()
    if not key:
        sys.exit("FOOTBALL_DATA_KEY secret is missing. Add it under Settings > Secrets and variables > Actions.")

    try:
        data = get_json(TABLE_URL, {"X-Auth-Token": key})
    except urllib.error.HTTPError as e:
        sys.exit(f"football-data.org returned {e.code}: {e.read()[:300]!r}")

    total = next(s for s in data["standings"] if s.get("type") == "TOTAL")
    season = (data.get("season") or {}).get("startDate", "")[:4]
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
            "yc": None,
            "rc": None,
        })

    try:
        with open(OUT) as f:
            old = json.load(f)
    except (FileNotFoundError, ValueError):
        old = {}

    # Start from the last known card counts.
    old_cards = {norm(t.get("name")): (t.get("yc"), t.get("rc")) for t in old.get("teams", [])}
    for t in teams:
        t["yc"], t["rc"] = old_cards.get(norm(t["name"]), (None, None))

    cards_at = old.get("cardsUpdatedAt")
    due = True
    if cards_at:
        try:
            due = now() - datetime.datetime.fromisoformat(cards_at) > datetime.timedelta(hours=CARDS_EVERY_HOURS)
        except ValueError:
            due = True
    if due and season:
        try:
            cards = fetch_cards(teams, season)
            for t in teams:
                if t["name"] in cards:
                    t["yc"], t["rc"] = cards[t["name"]]
            print(f"Cards: updated {len(cards)} of {len(teams)} teams from ESPN.")
            if cards:
                cards_at = now().isoformat(timespec="seconds")
        except Exception as e:  # never let ESPN problems stop the table update
            print(f"Cards: ESPN check failed ({e}); keeping the last known counts.")

    if old.get("teams") == teams and old.get("cardsUpdatedAt") == cards_at:
        print("Nothing changed.")
        return

    out = {
        "updatedAt": now().isoformat(timespec="seconds") if old.get("teams") != teams else old.get("updatedAt"),
        "cardsUpdatedAt": cards_at,
        "season": season,
        "teams": teams,
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"Saved: {teams[0]['shortName']} top, {teams[-1]['shortName']} bottom.")


if __name__ == "__main__":
    main()

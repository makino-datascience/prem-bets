# Prem Bets: setup

What's in this folder:

| File | What it does |
|---|---|
| `index.html` | The website: Google sign-in, picks, rankings, EPL table, commissioner tab |
| `standings.json` | The EPL table the site reads. The GitHub job keeps it up to date |
| `scripts/fetch_standings.py` | Fetches the table from football-data.org |
| `.github/workflows/standings.yml` | Runs that script every 30 minutes on GitHub |
| `firestore.rules` | Database security rules: hides picks until the lock and blocks late changes |

## 1. Firebase: paste the security rules

1. In the Firebase console, open **Build → Firestore Database → Rules**.
2. Delete what's there, paste in everything from `firestore.rules`, and click **Publish**.

## 2. GitHub: create the repository

1. Sign up or sign in at [github.com](https://github.com), then click **+ → New repository**.
2. Name it `prem-bets`, set it to **Public** (free GitHub Pages needs that), and click **Create repository**.
3. Click **uploading an existing file**, drag in `index.html`, `standings.json`, `README.md`, `firestore.rules` and the `scripts` folder, then click **Commit changes**.
4. Add the scheduled job by hand, because computers often hide the `.github` folder and it gets skipped when dragging:
   - Click **Add file → Create new file**.
   - In the name box type `.github/workflows/standings.yml` (the slashes create the folders).
   - Paste in the contents of `standings-workflow-copy.yml` (a visible copy of the same file), then click **Commit changes**.

## 3. GitHub: add the football-data.org key

1. In the repository, open **Settings → Secrets and variables → Actions → New repository secret**.
2. Name: `FOOTBALL_DATA_KEY`. Secret: the API key football-data.org emailed you. Click **Add secret**.
3. Open **Settings → Actions → General**, scroll to **Workflow permissions**, choose **Read and write permissions**, and click **Save**.

## 4. GitHub: turn on the website

1. Open **Settings → Pages**.
2. Under **Build and deployment**, set Source to **Deploy from a branch**, Branch to **main** and folder to **/ (root)**, then click **Save**.
3. After a minute or two the page shows your address: `https://YOUR-USERNAME.github.io/prem-bets/`.

## 5. Run the table job once

1. Open the **Actions** tab. If GitHub asks, click to enable workflows.
2. Click **Update EPL table → Run workflow → Run workflow**.
3. It should finish green within a minute. From then on it runs every 30 minutes by itself.

If it fails, open the run to see the message. The usual cause is a missing or mistyped `FOOTBALL_DATA_KEY`.

## 6. Firebase: allow sign-in from your website

1. In the Firebase console, open **Build → Authentication → Settings → Authorized domains**.
2. Click **Add domain** and enter `YOUR-USERNAME.github.io`.

## 7. Try it

1. Open your site, sign in with **rajatcool95@gmail.com**, and check that the **Commissioner** tab appears.
2. Make your picks and save them.
3. Send the link to your friends. Anyone with the link can sign in with Google and join. You can remove people from the Commissioner tab.

## Good to know

- **Lock time:** 9:00 AM UK time on October 10, 2026. Change it in the Commissioner tab. The database enforces it, so nobody can change picks after it, and nobody can see other people's picks before it.
- **Card counts:** the free football-data.org plan doesn't include cards. Enter each team's total in the Commissioner tab every week or two. ESPN's Premier League discipline stats page lists them.
- **Updating the table:** the job checks every 30 minutes, and GitHub Pages can take up to 10 more minutes to show the change.
- **Changing the commissioner:** edit the email in both `index.html` (`COMMISSIONER_EMAIL`) and `firestore.rules`, then publish the rules again.
- GitHub pauses scheduled jobs in repositories with no activity for 60 days. If the table stops updating, open the Actions tab and re-enable the job.

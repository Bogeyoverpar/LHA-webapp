# LHA League Manager

A Streamlit web app for the hockey league workflow:

1. Upload team rosters.
2. Upload a week-by-week schedule.
3. Open the current week.
4. Enter each final score and the shots faced by each starting goalie.
5. The app assigns goal scorers and 0/1/2 assists.
6. It automatically tracks standings, skater leaders, goalie results, save percentage and shutouts.
7. Export CSV tables or a complete JSON league backup.

## Import formats

### Rosters
Required columns:

- `Team`
- `Player`
- `Position`

Optional:

- `Line` — 1 to 4; default 3
- `Scoring` — 1 to 99; default 70
- `Playmaking` — 1 to 99; default 70
- `Active` — TRUE/FALSE; default TRUE

Use `G` for goalies. Typical skater positions are `LW`, `C`, `RW`, `LD`, `RD`.

### Schedule
Required:

- `Week`
- `Away`
- `Home`

Optional:

- `Date`

Team names must match the roster file.

## Run locally

Install Python 3.11+.

Open a terminal in this folder and run:

    python -m venv .venv

macOS/Linux:

    source .venv/bin/activate

Windows PowerShell:

    .venv\Scripts\Activate.ps1

Then:

    pip install -r requirements.txt
    streamlit run app.py

Streamlit will open the app in your browser.

## Put it on GitHub

1. Create a new GitHub repository, for example `lha-league-manager`.
2. In the repository, choose **Add file → Upload files**.
3. Upload:
   - `app.py`
   - `requirements.txt`
   - `.gitignore`
   - `README.md`
   - optionally the two sample CSV files
4. Commit the files to the `main` branch.

Or from a terminal:

    git init
    git add .
    git commit -m "Initial LHA League Manager"
    git branch -M main
    git remote add origin https://github.com/YOUR-USERNAME/lha-league-manager.git
    git push -u origin main

## Deploy as a web app with Streamlit Community Cloud

1. Sign in to Streamlit Community Cloud with GitHub.
2. Choose **Create app**.
3. Select your GitHub repository and `main` branch.
4. Set the entrypoint file to `app.py`.
5. Deploy.

The app does not need API keys for this version.

## Important persistence note

This first version deliberately uses a downloadable JSON league backup rather than depending on the web server's disk. That makes the league portable and avoids treating Streamlit Community Cloud's local filesystem as permanent storage.

At the end of a session, use **Backup / Export → Download league backup**. On a new session or deployment, upload that JSON file and choose **Restore backup**.

A later version can connect to a persistent database such as Supabase/PostgreSQL so every result is saved automatically across devices.

## Distribution model

Goal selection is weighted by:
- scoring rating
- line assignment
- position
- a small current-season performance component

Assist selection uses:
- playmaking rating
- line assignment
- position
- the same restrained season-learning component

The default assist distribution is:
- 8% unassisted
- 27% one assist
- 65% two assists

These values are stored in the app settings structure and can be expanded into a settings screen.

## Current scope

Included:
- roster upload
- schedule upload
- week-by-week game entry
- score entry
- starting goalie and shots-against entry
- scorer distribution
- 0/1/2 assists
- goalie saves and goals against
- W/L/OTL
- shutouts
- standings
- skater leaders
- goalie leaders
- game/scoring logs
- CSV exports
- complete JSON backup/restore

Natural next upgrades:
- edit/undo finalized games
- multiple goalies in one game
- scratches and game-specific lineups
- power-play / shorthanded / empty-net goals
- penalties
- playoff brackets
- end-of-season development
- career statistics
- awards
- draft/prospect integration
- persistent cloud database

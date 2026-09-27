# LHA League Manager v2

Replace your existing `app.py` with this version and update `requirements.txt`.

## Included
- East/West standings and top-four playoff format
- Playoff, division, elimination and magic-number tracking
- Commissioner manual standings/status/seed overrides
- Best-of-seven Division Semifinals (1v4, 2v3), Division Finals, and Meyers Memorial Cup Finals
- Editable/deletable games
- Manual scorer/assist edits
- Goalie corrections
- Fixed duplicate/season-learning weighting crash
- CSV encoding fallback for Excel-generated CSV files
- Roster validation
- JSON backup/restore
- Derived stats: edits rebuild standings and leaderboards from saved game records

## GitHub / Streamlit
Upload `app.py`, `requirements.txt`, `.gitignore`, and this README to your existing GitHub repository and commit them. If Streamlit Community Cloud is already linked to that repository and `app.py` is the entrypoint, it should redeploy from the new commit.

## Persistence
This version still uses Streamlit session state. Download the JSON backup after sessions you want to preserve. The next architectural upgrade should be a persistent database so league state survives app restarts automatically.

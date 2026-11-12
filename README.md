# PeerSpace

PeerSpace helps students discover activities, find other interested people, and form teams. This is a local course-project MVP built from scratch with Next.js, FastAPI, SQLAlchemy, and SQLite.

## What you need

- Python 3.10 or newer
- Node.js 20 or newer (Node 22 is recommended) and npm
- Two terminals, one for the backend and one for the frontend

The application creates an empty SQLite database automatically the first time the backend starts. The database file is local and is not committed to Git.

## Run locally

From the project root, create a virtual environment and install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The API runs at <http://127.0.0.1:8000>; its interactive documentation is at <http://127.0.0.1:8000/docs>. If the frontend cannot reach the backend, confirm both terminals are still running. The frontend's API address can be changed with `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

SQLite defaults to `peerspace.db` in the directory from which the backend is started. Set `DATABASE_URL` before starting the backend to use a different SQLite file, for example `sqlite:///./my-demo.db`. Start the backend from the project root so the location is predictable.

## Try the workflow

1. Choose **Find people** and search for an activity. You can browse without an account, select an existing activity, or create one if you cannot find it.
2. Sign up with an introduction, activity interests and plain skill tags. Topics, courses and experience are optional and can be edited later. Existing accounts may need to complete their profile after this upgrade.
3. Explore shows every activity plus a Low, Medium or High activity-fit estimate. On an activity page, review teams, create one or enter the looking pool. State the dates or recurring days you can attend for that activity; no general evenings/weekends field is used.
4. Request a team with date answers and motivation, or accept an owner invitation from the looking pool. Owners see a numeric match estimate, factor report and applicant answers before deciding. Required dates must be confirmed before approval or invitation acceptance.
5. Check **My teams** for memberships, looking pools, requests and invitations. **Notifications** shows updates and an unread count. Members can leave, and owners can remove members, transfer ownership, update the schedule or close the team. Only accepted members see contacts, group links and the private text thread.

You can use separate browser profiles or log out and back in to try the workflow as different users. Nothing is published to GitHub or the internet by running the app locally.

### Real opportunities and demo people

The local database can be populated with a small snapshot of real, sourced opportunities and **fictional** participants:

```powershell
python -m backend.seed_real_opportunities
```

The script first backs up the existing SQLite database, then adds five curated opportunity listings and eight fictional accounts. Demo profile and team names begin with `[DEMO]`; they are not real people and do not represent actual interest in the events. Existing records are not overwritten. The importer is safe to run again, but it does not refresh changing event details automatically.

For example, sign in as `maya.demo@peerspace.invalid` with password `DemoPeer2026!` to review a demo team, or use your own account to request to join one. All demo accounts use that same public test password, so they are for local testing only and must not be used for real personal information. Insights include demo data when present.

The event dates and registration conditions were checked against the linked organizer pages on 12 November 2026. Follow each listing's official link for current details. Imported listings keep the organizer's fuller schedule in their description when it cannot be reliably structured.

## Administrator and imports

First sign up normally. Then, from the project root with the backend environment active, grant that account administrator access:

```powershell
python -m backend.manage make-admin your-email@example.com
```

Log out and back in to see the Admin tab. An administrator can review reports and hide opportunities or profiles, or suspend an account. This command is intended for the local project operator; do not expose command-line access to untrusted users.

To import curated opportunities, prepare a JSON array with `title`, `description`, `category`, and optional `official_url`, `organizer`, and `event_date` in `YYYY-MM-DD` format. Categories are `hackathon`, `course_project`, `study_group`, and `trek_sport`:

```powershell
python -m backend.manage import-curated your-email@example.com path/to/opportunities.json
```

The RSS importer can read a public RSS 2.0 feed selected by the operator. Check the source's terms, relevance, and reliability before using it. The importer does not infer event dates from publication dates:

```powershell
python -m backend.manage import-rss your-email@example.com https://example.com/feed.xml hackathon
```

No live feed has been selected or verified yet. Imports skip invalid entries and duplicate official URLs, and they report how many were added or skipped. An import failure is shown in the terminal; existing records remain available.

## Tests and evaluation

From the project root, with backend dependencies installed:

```powershell
python -m pytest backend/tests -q
python -m backend.evaluation
```

The tests use temporary SQLite databases. They include a test where ten approvals compete for three remaining team slots. For frontend checks:

```powershell
cd frontend
npm run typecheck
npm run build
```

`analysis/matching_evaluation.ipynb` explains the reproducible 30-run comparison. It uses simulated data and evaluates the same score the matcher optimizes; its results do not demonstrate real-world compatibility or adoption. The course evidence matrix is in [docs/course-evidence.md](docs/course-evidence.md).

## Project map

- `backend/main.py` contains the API routes; `schemas.py` validates request inputs.
- `backend/models.py` and `database.py` define the SQLite records and connection.
- `backend/migrate.py` performs the repeatable SQLite upgrade on startup. Use `python -m backend.manage backup path/to/backup.db` before deploying a schema change.
- `backend/matching.py` contains the category weights and explanations.
- `backend/security.py` contains password and session-token helpers.
- `backend/manage.py` contains the local admin and import commands.
- `frontend/src/app` contains the pages, forms, views, and styles; `frontend/src/lib/api.ts` handles API requests and types.
- `backend/tests` contains API and concurrency tests.

## Current limitations

The current hosted version uses Railway with a persistent SQLite volume; the repository also runs locally. Session tokens are held in browser local storage; signup has no email verification or rate limiting. SQLite serializes membership writes using `BEGIN IMMEDIATE`; moving to another database requires a migration and new concurrency tests. Startup upgrades existing SQLite columns and converts old skill dictionaries; old general availability is retained only as legacy data and is never treated as confirmed date answers. Matching weights are initial, explainable rules rather than validated measures. The official course rubric and any real data-source permissions still need confirmation.

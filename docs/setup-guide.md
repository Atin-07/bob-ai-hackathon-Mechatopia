# Setup Guide

> **This file is read by the automated evaluation pipeline. Be precise and complete.**

## Prerequisites

- [ ] Python 3.10 – 3.12
- [ ] Node.js 18+ and npm
- [ ] Docker Desktop (or Docker Engine with the Compose plugin)
- [ ] Git
- [ ] Build tools for InsightFace: `sudo apt-get install python3-dev build-essential cmake` (Ubuntu/Debian) or `xcode-select --install` (macOS). On Windows, install "Microsoft C++ Build Tools".
- [ ] Internet access on first run (InsightFace downloads the `buffalo_l` model weights, about 300 MB)
- [ ] Free ports: `5432` (Postgres), `8000` (Core), `8001` (Person), `3008` (Ingestion), `5174` (Frontend)

No IBM cloud account or API key is needed to run this project.

## Environment Variables

Each service has its own `.env.example`. Copy it to `.env` in the same folder (commands are in the Installation section). The defaults work for a local run.

**`src/core/.env`**

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | Postgres URL (matches `docker-compose.yml`) | Yes |
| `SERVICE_KEY` | Shared secret for ingestion → core camera sync. Must equal the value in `src/ingestion/.env` | Yes |

**`src/person/.env`**

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | Same Postgres instance as Core | Yes |
| `CORE_ALERT_URL` | Core's `/alerts` endpoint, `http://localhost:8000/alerts` | Yes |
| `MATCH_THRESHOLD` | Cosine distance cutoff for a match (default `0.4`) | No |
| `ALERT_COOLDOWN_SECONDS` | Minimum gap between repeat alerts for the same camera and person (default `60`) | No |
| `CROP_STORAGE_DIR` | Where face crops are saved (default `./crops`) | No |
| `REFERENCE_PHOTO_DIR` | Where watchlist reference photos are saved (default `./reference_photos`) | No |

**`src/ingestion/.env`**

| Variable | Description | Required |
|---|---|---|
| `CATALOGUE_BASE_URL` | Camera catalogue (served by ingestion itself), `http://localhost:3008` | Yes |
| `FACE_AI_URL` | Person service batch endpoint, `http://localhost:8001/person/batch` | Yes |
| `GLS_REGISTRY_URL` | Core camera sync endpoint, `http://localhost:8000/cameras/gls-sync` | Yes |
| `SERVICE_KEY` | Must equal Core's `SERVICE_KEY` | Yes |
| `SERVER_PORT` | Ingestion's own port (`3008`) | Yes |
| `VEHICLE_AI_URL` | Vehicle AI endpoint. Not implemented in this submission, so leave the default (batches to it are just dropped and logged) | No |
| `TARGET_SAMPLE_FPS`, `BATCH_SIZE`, `MAX_ACTIVE_STREAMS`, … | Pipeline tuning (see `src/ingestion/readme.md`) | No |

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/TODO_GITHUB_USER/bob-ai-hackathon-mechatopia.git
cd bob-ai-hackathon-mechatopia

# 2. Start the database (PostgreSQL 15 + PostGIS + pgvector)
docker compose up -d --build

# 3. Core API dependencies
cd src/core
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # Windows: copy .env.example .env
cd ../..

# 4. Person service dependencies
cd src/person
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd ../..

# 5. Ingestion dependencies
cd src/ingestion
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd ../..

# 6. Frontend dependencies
cd src/frontend
npm install
cd ../..
```

Tables and the pgvector extension are created automatically when Core and the Person service start. There are no migration commands.

## Running the Application

Start the services in this order, each in its own terminal, with that service's venv activated.

```bash
# Terminal 1 — Core API (creates the tables)
cd src/core
uvicorn app.main:app --port 8000

# Terminal 2 — Person service (wait for "DB initialized")
cd src/person
uvicorn main:app --port 8001

# Terminal 3 — Ingestion (serves the catalogue and syncs cameras into Core)
cd src/ingestion
python main.py

# Terminal 4 — Frontend
cd src/frontend
npm run dev
```

The application will be available at: `http://localhost:5174`

## Verify It Works

1. `curl http://localhost:8000/health` returns `{"status":"healthy","service":"core_backend"}`.
2. `curl http://localhost:8001/health` returns `{"status":"ok"}`.
3. `curl http://localhost:3008/api/ingest` returns the camera catalogue as JSON.
4. Open `http://localhost:5174`. After ingestion's first sync (about 30 s) the **Cameras** page lists cameras and the map shows them.
5. Interactive API docs: `http://localhost:8000/docs` (Core).

## Quick Demo

Add a person to the watchlist, then upload a photo of them to search. Sample photos are in `src/photos/`.

```bash
# Add a missing person (from src/person, venv active)
python add_person.py missing "Demo Missing Person" ../photos/person1_missing.png

# Add a wanted person
python add_person.py wanted "Demo Wanted Person" ../photos/person2_wanted.jpeg
```

Then in the dashboard:

1. Open **Search**, upload `src/photos/person1_missing.png` and view the sightings, timeline and trail map.
2. Watch the **Alerts** page. When a watchlisted face appears in a live stream, a toast appears and the alert is added to the feed.

You can also load the sample cameras directly into Core instead of waiting for ingestion:

```bash
curl -X POST http://localhost:8000/cameras/bulk-import-json \
  -H "Content-Type: application/json" \
  -d @src/data/sample_cameras.json
```

Live alerts need camera streams that are actually reachable. The RTSP URLs in the sample data point at demo hosts, so replace them with your own RTSP source to see live detections.

## Running Tests

There are no automated tests in this submission yet. Use the "Verify It Works" steps above as the smoke test.

## Troubleshooting

| Issue | Solution |
|---|---|
| `connection refused` on port 5432 | The database is not up. Run `docker compose up -d --build` and check `docker ps` shows `netra_postgis`. |
| `extension "vector" is not available` | The database image was not built. Run `docker compose up -d --build` (the Dockerfile installs pgvector and PostGIS). |
| `pip install insightface` fails with a compiler error | Install build tools (see Prerequisites), then re-run `pip install -r requirements.txt`. |
| First Person service start is slow | InsightFace is downloading `buffalo_l` weights. Wait for it to finish (needs internet). |
| Cameras page is empty | Wait about 30 s for ingestion's first sync, check that `SERVICE_KEY` matches in `core/.env` and `ingestion/.env`, or use the bulk-import command above. |
| `401 Invalid or missing X-Service-Key` in ingestion logs | `SERVICE_KEY` differs between Core and Ingestion. Make them identical and restart both. |
| No alerts appear | Check the Person service is running on 8001, `FACE_AI_URL` points at `/person/batch`, `CORE_ALERT_URL` is correct, the watchlist has at least one person, and the camera streams are reachable. |
| Person events fail with a foreign key error | The camera does not exist in Core yet. Let ingestion sync first, or bulk-import cameras. |
| Frontend cannot reach the API | Core must be on port 8000 and Person on 8001. Ports are set in `src/frontend/src/config.ts`. |
| `Address already in use` | Another process holds the port. Stop it or change the port in the matching `.env` / uvicorn command (and in `config.ts`). |
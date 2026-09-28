# Person Service

Detects faces in incoming camera frames, checks them against missing/wanted
watchlists, raises alerts on a match, stores every detection for later
search, and exposes a photo-based search endpoint.

## Architecture

```
POST /person/batch (from Ingestion)
        │
        ▼
batch_receiver.py -- decode, push to internal queue, return 202 immediately
        │
        ▼
frame_worker.py (background) -- pulls frames, calls:
        │
        ├──► detection_recognition/detect_person.py -- process_frame()
        │     returns faces + 512-dim embeddings + crops
        │
        ├──► event_store.py -- ALWAYS writes a row to person_events
        │
        ├──► watchlist_store.py -- loads person_missing + person_wanted
        │     into one combined list
        │
        ├──► matching/match_watchlist.py -- match_watchlist()
        │     compares embedding against the combined list
        │
        └──► if matched + not on cooldown:
              alert_store.py -- writes to person_alerts
              send_to_core.py -- POSTs to core's /alerts endpoint
              (core pushes it live to the frontend over WebSocket --
               NOT something this service does directly)

GET /person/search -- separate, on-demand path:
        upload a photo -> embed it -> nearest-neighbor query directly
        against person_events -> returns matching sightings with
        camera + timestamp (does NOT call match_watchlist)

Scheduled job (retention_cleanup.py):
        deletes person_events older than 48h with no watchlist match
```

## File structure

```
person/
├── main.py                      # FastAPI app, starts worker + cleanup job
├── db.py                         # DB engine/session (Postgres + pgvector)
├── config.py                      # env-based settings
├── schemas.py                      # request/response models
├── ingestion/batch_receiver.py       # POST /person/batch
├── worker/frame_worker.py              # background processing loop
├── watchlist/watchlist_store.py          # loads missing+wanted from DB
├── events/
│   ├── event_store.py                      # writes person_events
│   └── search_person.py                      # GET/POST /person/search
├── alerts/
│   ├── cooldown.py                              # per (camera,person) cooldown
│   ├── alert_store.py                             # writes person_alerts
│   └── send_to_core.py                              # POST to core
├── jobs/retention_cleanup.py                          # scheduled cleanup
├── detection_recognition/                               # face detection + embedding
└── matching/                                              # watchlist matching + reference embedding
```

## Setup

```bash
cd cctv-platform/person
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`insightface` needs build tools on some systems:
```bash
# Ubuntu/Debian
sudo apt-get install python3-dev build-essential cmake
# Mac
xcode-select --install
```

First run downloads the `buffalo_l` model weights automatically — needs
internet access the first time.

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | — | Postgres connection string. **Shared with the vehicle section** — same instance, different tables (`person_*` vs `vehicle_*`) |
| `CORE_ALERT_URL` | — | Core's `/alerts` endpoint. Must point at a real, running core service for alerts to actually reach the frontend |
| `MATCH_THRESHOLD` | `0.4` | Cosine distance cutoff for a watchlist match |
| `ALERT_COOLDOWN_SECONDS` | `60` | Minimum gap between repeat alerts for the same (camera, person) pair |
| `CROP_STORAGE_DIR` | `./crops` | Where face crop JPEGs are saved |

## Database

Uses 4 tables, all prefixed `person_` (see `person_schema.sql` for the
full DDL): `person_missing`, `person_wanted`, `person_events`,
`person_alerts`. `init_db()` creates these automatically on startup if
they don't exist (`CREATE TABLE IF NOT EXISTS`), plus the pgvector
extension and similarity-search indexes.

## Run it

```bash
uvicorn main:app --reload --port 8001
```

Point the ingestion service's `FACE_AI_URL` at
`http://localhost:8001/person/batch`.

## Endpoints

| Endpoint | Called by | Purpose |
|---|---|---|
| `POST /person/batch` | Ingestion service only | Receives frame batches. Returns `202` immediately — does no detection/DB work in the request itself |
| `POST /person/search` | Frontend, on demand | Upload a photo, get back a list of past sightings across cameras |
| `GET /health` | Monitoring | Liveness check |

**There is no endpoint here for real-time alerts.** Alerts are pushed
from this service to core via `send_to_core.py`; the frontend gets them
live from **core's WebSocket**, not from anything in this service.

## Design notes worth remembering

- Every detected face gets a `person_events` row, matched or not.
- Alerts are deduplicated via cooldown; events never are — the repetition
  is what powers the search/timeline feature.
- Only face crops are stored, never full frames.
- `detection_recognition/` and `matching/` are pure functions — no DB, no
  network calls. All storage and orchestration lives in the files listed
  above.
- `batch_receiver.py` must stay fast (no ML/DB work inline) since the
  ingestion service waits synchronously for its response before sending
  the next batch.
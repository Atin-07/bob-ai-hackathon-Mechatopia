# Solution Overview

## What We Built

Netra is a set of small services that together turn many separate CCTV cameras into one searchable, alerting system for finding people. It has four parts:

- **Core** keeps the camera registry, receives alerts and broadcasts them live to the dashboard.
- **Ingestion** connects to every live camera, samples and batches frames, and forwards them for analysis.
- **Person service** finds faces, turns them into numeric fingerprints (embeddings), checks them against missing/wanted watchlists, and answers "where has this person been seen?" queries.
- **Frontend** is the operator dashboard: camera map, live alerts and photo search.

## How It Works

1. **Register cameras.** Camera metadata (location, department, RTSP/WebRTC/HLS URLs) is served by a catalogue endpoint. Ingestion polls it every 30 s and syncs the list into the Core registry.
2. **Ingest streams.** Ingestion opens one RTSP worker per online camera, samples about 5 frames per second, keeps them in bounded per-camera buffers, and groups them into batches of 4 frames from mixed cameras.
3. **Dispatch.** Each batch is JPEG-encoded once and sent to the Person service. Each destination has its own worker and bounded queue, so a slow consumer drops batches instead of stalling every camera.
4. **Detect and embed.** The Person service returns `202 Accepted` immediately and processes frames in a background worker. InsightFace (`buffalo_l`) detects every face and produces a 512-dimensional ArcFace embedding.
5. **Store every sighting.** Each detection is written to `person_events` (camera, timestamp, bounding box, embedding, face crop) in PostgreSQL with pgvector.
6. **Match the watchlist.** Each embedding is compared by cosine distance against all `person_missing` and `person_wanted` embeddings. A match under the threshold (default 0.4) creates a `person_alerts` row, unless the same person was already alerted on that camera within the cooldown (default 60 s).
7. **Alert live.** The Person service posts the alert to Core, which broadcasts it over WebSocket. The dashboard shows a toast and adds it to the alert feed.
8. **Search on demand.** An operator uploads a photo, the photo is embedded, and a pgvector nearest-neighbour query over `person_events` returns every matching sighting with camera and time, shown as a timeline and a trail on the map.
9. **Clean up.** A scheduled job deletes `person_events` older than 48 hours that never matched a watchlist entry, together with their face crops.

## Architecture Diagram

> See [`architecture.md`](architecture.md) for the detailed diagram.

```
Cameras (RTSP) → Ingestion → Person service → PostgreSQL + pgvector
                                   │                    ▲
                                   ▼                    │
                              Core API ──WebSocket──► React dashboard ──► /person/search
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Accept batches with `202` and process in a background queue | Ingestion waits for each HTTP response, so a slow response would back up every camera. Returning immediately keeps the pipeline moving. |
| Frames stay as raw arrays until one JPEG encode right before dispatch | Avoids repeated encode/decode cost and keeps CPU use predictable across many cameras. |
| Bounded per-camera buffers and per-destination queues that drop when full | Under overload we prefer losing a few frames to unbounded memory growth or one camera starving the rest. |
| One pgvector `person_events` table serves both live matching and photo search | A single index and a single source of truth. Search over historical sightings needs no extra pipeline. |
| Every detection is stored, not just matches | This is what makes "where was this person earlier?" possible after a photo arrives later. |
| Per-(camera, person) alert cooldown | A person standing in view would otherwise raise an alert on every frame. |
| 48-hour retention on unmatched detections | Limits how much biometric data we hold about people who are not on any list. |
| Person service writes its own rows and only pushes alerts to Core | Core stays a thin registry and broadcast layer, and the two services share a database but not code paths. |
| A mock catalogue served over real HTTP | Swapping in a real government catalogue later is a config change (`CATALOGUE_BASE_URL`), not a code change. |

## IBM Technologies Used

- **IBM Bob:** TODO — describe exactly how the team used Bob (for example, which modules or files it helped design or generate, and where it changed the outcome). Replace this line before submitting. The evaluation rubric checks that Bob is genuinely used, so be specific and honest.

## What the User Experience Looks Like

The operator opens the dashboard and sees cameras on a map with their status. A red toast appears when a watchlisted face is seen, showing the person, category (missing or wanted), camera and similarity score. To trace someone, the operator uploads a photo on the search page and gets a timeline of sightings and a movement trail across the camera map.
# Ingestion Service

Pulls camera feeds, samples and batches frames, and forwards them to both
the Vehicle AI and Person (Face) AI services.

## What this does

```
CatalogClient (polls camera registry)
    -> StreamManager (one RTSP worker per live camera)
    -> FrameSampler (per camera, ~5fps, PTS-driven)
    -> BufferManager (per-camera bounded queues)
    -> Batcher (groups frames into batches of 4, mixed cameras)
    -> encode_batch (raw frame -> JPEG -- the ONLY place encoding happens)
    -> PayloadBuilder (base64 + JSON shape for Vehicle/Face AI)
    -> AIDispatcher (sends the same batch to both Vehicle AI and Face AI,
                      one worker per destination, bounded queues)
```

Frames stay as raw numpy arrays through decode → sample → buffer → batch.
JPEG encoding happens once, right before dispatch. Nothing upstream ever
touches JPEG/base64.

## Setup

```bash
cd cctv-platform/ingestion
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` as needed — the defaults point at `localhost` for the
downstream Vehicle AI / Face AI services, which won't exist until those
teams run their own services locally.

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `CATALOGUE_BASE_URL` | `http://localhost:8000` | Where the camera registry lives |
| `CATALOGUE_REFRESH_INTERVAL_SECONDS` | `30` | How often to re-poll for camera list changes |
| `RTSP_TRANSPORT` | `tcp` | RTSP transport protocol |
| `MAX_ACTIVE_STREAMS` | `10` | Cap on concurrent camera connections |
| `RECONNECT_INITIAL_BACKOFF_SECONDS` / `RECONNECT_MAX_BACKOFF_SECONDS` | `2` / `30` | Backoff on dropped streams |
| `TARGET_SAMPLE_FPS` | `5` | Frames per second sampled per camera |
| `CAMERA_BUFFER_MAX_SIZE` | `30` | Per-camera buffer cap before frames drop |
| `BATCH_SIZE` | `4` | Frames per batch sent downstream |
| `BATCH_MAX_WAIT_SECONDS` | `1` | Max wait before flushing a partial batch |
| `VEHICLE_AI_URL` | `http://localhost:9001/process` | Vehicle AI's ingest endpoint |
| `FACE_AI_URL` | `http://localhost:9002/process` | **Should point at the Person service's `/person/batch` endpoint** |
| `DISPATCH_TIMEOUT_SECONDS` | `5` | HTTP timeout per dispatch call |
| `DISPATCH_QUEUE_MAX_SIZE` | `50` | Per-destination queue cap — full queue = dropped batches |
| `GLS_REGISTRY_URL` / `GLS_PUSH_INTERVAL_SECONDS` | — | Registry sync settings |
| `SERVER_HOST` / `SERVER_PORT` | `0.0.0.0` / `8000` | This service's own bind address |

**Important:** `FACE_AI_URL` must point at wherever the Person service is
actually running (e.g. `http://localhost:8001/person/batch`), not the
placeholder default.

## Run it

```bash
python main.py
```

## Behavior worth knowing

- **Backpressure is real**: each downstream destination (Vehicle AI, Face
  AI) has its own worker and bounded queue. The worker sends one batch,
  *waits for the HTTP response*, then sends the next. If a downstream
  service is slow, its queue fills up (`DISPATCH_QUEUE_MAX_SIZE`) and
  further batches for that destination are **silently dropped** (logged,
  not retried). Downstream services must respond fast — see the Person
  service README's note on this.
- Both Vehicle AI and Face AI receive the **same batch** — same frames,
  same metadata — dispatched independently to each.
- JPEG quality is fixed at 85 in `frame_encoder.py`.

## Payload shape sent downstream

```json
POST <VEHICLE_AI_URL or FACE_AI_URL>
{
  "frames": [
    {
      "camera_id": "cam_01",
      "organization_id": "org_1",
      "pts_ms": 123456.0,
      "width": 1920,
      "height": 1080,
      "format": "jpeg",
      "frame": "<base64 JPEG string>"
    }
  ]
}
```
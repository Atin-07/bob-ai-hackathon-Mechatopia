# 🚀 Netra — Integrated CCTV Video Management & Person Tracking

> Unified camera registry + real-time face recognition that turns thousands of siloed CCTV feeds into one searchable, alerting platform.

---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | Mechatopia |
| **Track** | AI |
| **Team Lead** | TODO_LEAD_NAME — TODO_LEAD_EMAIL |
| **Members** | TODO_LEAD_NAME, TODO_MEMBER_2_NAME, TODO_MEMBER_3_NAME |

---

## 🎯 Problem Statement

Police, transport and municipal departments each run their own CCTV cameras in separate systems. When a person goes missing or a suspect is wanted, operators have to manually scrub footage camera by camera, which costs hours when minutes matter.

---

## 💡 Solution

Netra ingests live RTSP streams from a central camera registry, samples and batches frames, and runs face detection and recognition (InsightFace ArcFace, 512-dim embeddings stored in PostgreSQL + pgvector). Every face is matched against missing/wanted watchlists in real time and raises a live WebSocket alert, and operators can upload any photo to find all past sightings across cameras on a map and timeline.

---

## ✨ Key Features

- **Multi-camera ingestion:** per-camera RTSP workers, ~5 fps sampling, bounded buffers, batching and back-pressure-aware dispatch.
- **Face recognition:** InsightFace `buffalo_l` detection + 512-dim ArcFace embeddings for every sampled frame.
- **Live watchlist alerts:** cosine-distance matching against missing/wanted persons, per-camera cooldown, alerts pushed over WebSocket.
- **Photo-based person search:** upload a photo, get every sighting across cameras with a timeline and trail map.
- **Camera registry + dashboard:** Leaflet map, bulk import/export, gap analysis and alert feed in React.
- **Privacy-aware retention:** unmatched detections are deleted automatically after 48 hours.

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python, TypeScript |
| **Frameworks** | FastAPI, React 18, Vite, SQLAlchemy, Leaflet |
| **IBM Technologies** | IBM Bob |
| **Databases** | PostgreSQL, PostGIS, pgvector |
| **Other** | Docker Compose, InsightFace, ONNX Runtime, OpenCV, WebSockets, GitHub Actions |

---

## 📁 Repository Structure

```
├── src/
│   ├── core/            # Core API: camera registry, alerts (WebSocket), person events  (port 8000)
│   ├── ingestion/       # RTSP ingestion, sampling, batching, dispatch                   (port 3008)
│   ├── person/          # Face detection, recognition, watchlist matching, search        (port 8001)
│   ├── frontend/        # React + Vite operator dashboard                                (port 5174)
│   ├── data/            # Sample cameras, watchlist and users
│   └── photos/          # Sample reference photos
├── docs/                # Written documentation
│   ├── problem-statement.md
│   ├── solution-overview.md
│   ├── architecture.md
│   └── setup-guide.md
├── demo/                # Demo video link, live demo note, screenshots
├── presentation/        # Slide deck
├── docker-compose.yml   # PostgreSQL + PostGIS + pgvector
└── submission.yaml      # Structured submission metadata
```

---

## ⚡ How to Run

Full details, prerequisites and troubleshooting are in [`docs/setup-guide.md`](docs/setup-guide.md).

```bash
# 1. Clone the repo
git clone https://github.com/TODO_GITHUB_USER/bob-ai-hackathon-mechatopia.git
cd bob-ai-hackathon-mechatopia

# 2. Start the database (PostgreSQL + PostGIS + pgvector)
docker compose up -d --build

# 3. Core API (terminal 1)
cd src/core && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn app.main:app --port 8000

# 4. Person service (terminal 2)
cd src/person && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn main:app --port 8001

# 5. Ingestion service (terminal 3)
cd src/ingestion && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
python main.py

# 6. Frontend (terminal 4)
cd src/frontend && npm install && npm run dev
# open http://localhost:5174
```

On Windows, activate the virtual environment with `venv\Scripts\activate`.

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🌐 Live Demo | [See demo/live-demo-url.txt](demo/live-demo-url.txt) |
| 🖼️ Screenshots | [See demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [See presentation/slides.pdf](presentation/) |

---

## ⚠️ Known Limitations

- Vehicle AI (number plate recognition) is wired into ingestion but not implemented in this submission.
- Authentication is only a shared service key between services. There is no operator login and CORS is open, so this is a prototype, not production-ready.
- Face inference runs on CPU by default, and the sample cameras point at demo RTSP hosts.
- No automated tests yet.

---

## 🏅 What We're Most Proud Of

The whole pipeline runs end to end: camera frames flow through ingestion, face recognition and watchlist matching, and arrive as a live alert on the dashboard. One pgvector table serves both real-time matching and after-the-fact photo search, and ingestion handles back-pressure explicitly. Those are the parts most worth reading in `src/person/` and `src/ingestion/pipeline/`.

---
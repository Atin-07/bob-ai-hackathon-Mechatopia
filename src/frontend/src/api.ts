import { CORE_API, PERSON_API, CORE_WS } from "./config";
import type {
  Camera,
  PersonSearchResult,
  FeedItem,
  DashboardSummary,
  GapAnalysis,
  PersonAlert,
} from "./types";

// ── Cameras ─────────────────────────────────────────────
export async function fetchCameras(params?: Record<string, string>): Promise<Camera[]> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  const res = await fetch(`${CORE_API}/cameras${qs}`);
  if (!res.ok) throw new Error(`Failed to fetch cameras: ${res.status}`);
  return res.json();
}

export async function fetchCamera(cameraId: string): Promise<Camera> {
  const res = await fetch(`${CORE_API}/cameras/${cameraId}`);
  if (!res.ok) throw new Error(`Camera not found: ${res.status}`);
  return res.json();
}

// ── Person search ───────────────────────────────────────
export async function searchPerson(
  file: File,
  topK = 50
): Promise<PersonSearchResult> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${PERSON_API}/person/search?top_k=${topK}`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

// ── Alerts ──────────────────────────────────────────────
export async function fetchAlertFeed(): Promise<FeedItem[]> {
  const res = await fetch(`${CORE_API}/alerts/feed`);
  if (!res.ok) throw new Error(`Failed to fetch alerts: ${res.status}`);
  return res.json();
}

export async function fetchPersonAlerts(): Promise<PersonAlert[]> {
  const res = await fetch(`${CORE_API}/alerts/person`);
  if (!res.ok) throw new Error(`Failed to fetch person alerts: ${res.status}`);
  return res.json();
}

// ── WebSocket ───────────────────────────────────────────
export function connectAlerts(onAlert: (msg: unknown) => void): () => void {
  let ws: WebSocket;
  let stopped = false;

  const open = () => {
    if (stopped) return;
    ws = new WebSocket(`${CORE_WS}/alerts/ws`);
    ws.onmessage = (e) => onAlert(JSON.parse(e.data));
    ws.onclose = () => {
      if (!stopped) setTimeout(open, 2000);
    };
    ws.onerror = () => ws.close();
  };

  open();

  return () => {
    stopped = true;
    ws?.close();
  };
}

// ── Dashboard ───────────────────────────────────────────
export async function fetchSummary(): Promise<DashboardSummary> {
  const res = await fetch(`${CORE_API}/admin/summary`);
  if (!res.ok) throw new Error(`Failed to fetch summary: ${res.status}`);
  return res.json();
}

// ── Gap analysis ────────────────────────────────────────
export async function fetchGapAnalysis(): Promise<GapAnalysis> {
  const res = await fetch(`${CORE_API}/cameras/reports/gap-analysis`);
  if (!res.ok) throw new Error(`Failed to fetch gap analysis: ${res.status}`);
  return res.json();
}

// ── Health checks ───────────────────────────────────────
export async function checkHealth(): Promise<{
  core: boolean;
  person: boolean;
}> {
  const check = async (url: string) => {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(3000) });
      return r.ok;
    } catch {
      return false;
    }
  };
  const [core, person] = await Promise.all([
    check(`${CORE_API}/health`),
    check(`${PERSON_API}/health`),
  ]);
  return { core, person };
}

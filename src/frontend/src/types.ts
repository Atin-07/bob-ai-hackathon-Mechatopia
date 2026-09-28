// ── Camera ──────────────────────────────────────────────
export interface CameraLocation {
  latitude: number | null;
  longitude: number | null;
  address: string;
}

export interface CameraStream {
  rtsp?: string;
  webrtc?: string;
  hls?: string;
}

export interface Camera {
  camera_id: string;
  organization_id: string;
  organization_name?: string;
  name: string;
  status: "online" | "offline" | "maintenance" | "inactive";
  location: CameraLocation;
  camera_type: string;
  properties: Record<string, unknown>;
  stream: CameraStream;
  department: string;
  district: string;
  vms_vendor?: string;
  storage_type?: string;
  retention_days?: number;
  install_date?: string;
  last_health_check?: string;
}

// ── Person search ───────────────────────────────────────
export interface PersonMatch {
  event_id: string;
  camera_id: string;
  detected_at: string;
  similarity_score: number;
  crop_image_path: string | null;
}

export interface PersonSearchResult {
  matches: PersonMatch[];
}

// ── Enriched match (joined with Camera metadata) ────────
export interface EnrichedMatch extends PersonMatch {
  camera_name: string;
  latitude: number | null;
  longitude: number | null;
  address: string;
}

// ── Alerts ──────────────────────────────────────────────
export interface PersonAlert {
  source: "person";
  alert_id: string;
  event_id: string;
  person_id?: string;
  missing_id?: string | null;
  wanted_id?: string | null;
  camera_id: string;
  category: "missing" | "wanted";
  similarity_score: number;
  crop_image_path?: string | null;
  status?: string;
  created_at?: string;
}

export interface VehicleAlert {
  source: "vehicle";
  id: number;
  event_id: number;
  plate_number: string;
  camera_id: string;
  alert_type: string;
  severity: string;
  details: string;
  status: string;
  triggered_at: string;
}

export type AlertMessage = PersonAlert | VehicleAlert;

export interface FeedItem {
  source: "person" | "vehicle";
  id: string | number;
  camera_id: string;
  headline: string;
  details: string | null;
  severity: string;
  status: string;
  timestamp: string;
}

// ── Dashboard summary ───────────────────────────────────
export interface DashboardSummary {
  total_cameras: number;
  total_users: number;
  total_vehicle_events: number;
  total_person_events: number;
  total_alerts: number;
  watchlist_entries: number;
}

// ── Gap analysis ────────────────────────────────────────
export interface GapAnalysis {
  cameras_per_district: { district: string; count: number }[];
  cameras_per_department: { department: string; count: number }[];
  flagged_for_attention: {
    camera_id: string;
    name: string;
    district: string;
    status: string;
  }[];
  total_cameras: number;
}

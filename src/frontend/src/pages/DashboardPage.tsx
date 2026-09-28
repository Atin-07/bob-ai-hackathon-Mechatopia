import { useEffect, useState } from "react";
import {
  Camera as CameraIcon,
  Users,
  Car,
  Bell,
  ShieldAlert,
  Activity,
} from "lucide-react";
import { fetchSummary, fetchCameras, fetchAlertFeed, connectAlerts } from "../api";
import { showToast } from "../components/ToastContainer";
import ToastContainer from "../components/ToastContainer";
import CameraMap from "../components/CameraMap";
import type { Camera, DashboardSummary, FeedItem, AlertMessage } from "../types";
import { format } from "date-fns";

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const [s, c, f] = await Promise.all([
          fetchSummary().catch(() => null),
          fetchCameras().catch(() => []),
          fetchAlertFeed().catch(() => []),
        ]);
        if (!mounted) return;
        if (s) setSummary(s);
        setCameras(c);
        setFeed(f);
      } catch (err) {
        console.error("Dashboard load failed:", err);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();

    // Live alerts
    const disconnect = connectAlerts((msg) => {
      const alert = msg as AlertMessage;
      if (alert.source === "person") {
        showToast(
          alert.alert_id,
          `${alert.category} person detected on ${alert.camera_id}`,
          alert.category
        );
      }
    });

    return () => {
      mounted = false;
      disconnect();
    };
  }, []);

  if (loading) return <div className="spinner" />;

  const onlineCount = cameras.filter((c) => c.status === "online").length;
  const offlineCount = cameras.filter((c) => c.status === "offline").length;

  return (
    <div>
      <ToastContainer />
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Real-time surveillance system overview</p>
      </div>

      {/* Stats */}
      <div className="stat-grid">
        <div className="stat-card">
          <span className="stat-label">
            <CameraIcon size={14} style={{ marginRight: 4, verticalAlign: "middle" }} />
            Total Cameras
          </span>
          <span className="stat-value">{summary?.total_cameras ?? cameras.length}</span>
          <span style={{ fontSize: "0.75rem", color: "var(--green)" }}>
            {onlineCount} online · {offlineCount} offline
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">
            <Users size={14} style={{ marginRight: 4, verticalAlign: "middle" }} />
            Person Events
          </span>
          <span className="stat-value">{summary?.total_person_events?.toLocaleString() ?? "—"}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">
            <Car size={14} style={{ marginRight: 4, verticalAlign: "middle" }} />
            Vehicle Events
          </span>
          <span className="stat-value">{summary?.total_vehicle_events?.toLocaleString() ?? "—"}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">
            <Bell size={14} style={{ marginRight: 4, verticalAlign: "middle" }} />
            Total Alerts
          </span>
          <span className="stat-value">{summary?.total_alerts ?? feed.length}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">
            <ShieldAlert size={14} style={{ marginRight: 4, verticalAlign: "middle" }} />
            Watchlist
          </span>
          <span className="stat-value">{summary?.watchlist_entries ?? "—"}</span>
        </div>
      </div>

      {/* Map + Recent Alerts */}
      <div className="two-col" style={{ marginBottom: 24 }}>
        <div className="card">
          <h3 className="card-title">
            <Activity size={16} /> Camera Locations
          </h3>
          <CameraMap cameras={cameras} height="380px" />
        </div>

        <div className="card" style={{ maxHeight: 440, overflow: "auto" }}>
          <h3 className="card-title">
            <Bell size={16} /> Recent Alerts
          </h3>
          {feed.length === 0 ? (
            <div className="empty-state">No alerts yet</div>
          ) : (
            feed.slice(0, 20).map((item) => (
              <div className="alert-item" key={`${item.source}-${item.id}`}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span className={`badge ${item.severity?.toLowerCase()}`}>
                      {item.severity}
                    </span>
                    <span className={`badge ${item.source}`}>{item.source}</span>
                  </div>
                  <div style={{ fontWeight: 600, fontSize: "0.85rem" }}>
                    {item.headline}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: 2 }}>
                    {item.camera_id} · {format(new Date(item.timestamp), "MMM d, HH:mm:ss")}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

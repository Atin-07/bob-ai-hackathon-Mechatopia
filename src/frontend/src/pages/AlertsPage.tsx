import { useEffect, useState, useRef } from "react";
import {
  Bell,
  AlertTriangle,
  User,
  Car,
  RefreshCw,
  Filter,
} from "lucide-react";
import { fetchAlertFeed, connectAlerts } from "../api";
import ToastContainer, { showToast } from "../components/ToastContainer";
import type { FeedItem, AlertMessage } from "../types";
import { format } from "date-fns";

export default function AlertsPage() {
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState<"all" | "person" | "vehicle">("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const wsRef = useRef<(() => void) | null>(null);

  const loadFeed = async () => {
    setLoading(true);
    try {
      const data = await fetchAlertFeed();
      setFeed(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFeed();

    // WebSocket – prepend new alerts to the list
    const disconnect = connectAlerts((msg) => {
      const alert = msg as AlertMessage;

      const item: FeedItem = {
        source: alert.source,
        id: alert.source === "person" ? alert.alert_id : alert.id,
        camera_id: alert.camera_id,
        headline:
          alert.source === "person"
            ? `${alert.category} person match (${(alert.similarity_score * 100).toFixed(0)}% similarity)`
            : `${alert.alert_type} — ${alert.plate_number}`,
        details: alert.source === "vehicle" ? alert.details : null,
        severity:
          alert.source === "person"
            ? alert.category === "wanted"
              ? "HIGH"
              : "MEDIUM"
            : alert.severity,
        status: alert.source === "person" ? "new" : alert.status,
        timestamp: new Date().toISOString(),
      };

      setFeed((prev) => [item, ...prev]);

      // Toast
      showToast(
        String(item.id),
        `${item.headline} on ${item.camera_id}`,
        alert.source === "person" ? alert.category : "vehicle"
      );
    });
    wsRef.current = disconnect;

    return () => {
      disconnect();
    };
  }, []);

  const filtered = feed.filter((item) => {
    if (sourceFilter !== "all" && item.source !== sourceFilter) return false;
    if (severityFilter !== "all" && item.severity?.toUpperCase() !== severityFilter)
      return false;
    return true;
  });

  return (
    <div>
      <ToastContainer />
      <div className="page-header">
        <h1>Live Alerts &amp; Watchlist Log</h1>
        <p>Real-time WebSocket alerts stream and historical log</p>
      </div>

      <div className="filter-bar">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Filter size={15} color="var(--text-dim)" />
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value as "all" | "person" | "vehicle")}
          >
            <option value="all">All sources (Person &amp; Vehicle)</option>
            <option value="person">Person Watchlist</option>
            <option value="vehicle">Vehicle ANPR</option>
          </select>
        </div>

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
        >
          <option value="all">All severities</option>
          <option value="HIGH">High Severity</option>
          <option value="MEDIUM">Medium Severity</option>
          <option value="LOW">Low Severity</option>
        </select>

        <button className="btn btn-outline" onClick={loadFeed}>
          <RefreshCw size={14} /> Refresh Feed
        </button>

        <div style={{ marginLeft: "auto", fontSize: "0.85rem", color: "var(--text-dim)", fontWeight: 600 }}>
          {filtered.length} total event{filtered.length !== 1 ? "s" : ""}
        </div>
      </div>

      {loading && <div className="spinner" />}

      {!loading && filtered.length === 0 && (
        <div className="card empty-state" style={{ padding: "64px 20px" }}>
          <Bell size={48} style={{ opacity: 0.3 }} />
          <p style={{ marginTop: 12 }}>No alerts matching filters. Live detections will appear automatically.</p>
        </div>
      )}

      {!loading && filtered.length > 0 && (
        <div className="card" style={{ padding: 0 }}>
          {filtered.map((item) => {
            const key = `${item.source}-${item.id}`;
            const isNew = item.status === "new";
            const isPerson = item.source === "person";

            return (
              <div className={`alert-item ${isNew ? "new" : ""}`} key={key}>
                <div
                  className="alert-icon-avatar"
                  style={{
                    background: isPerson
                      ? "var(--accent-glow)"
                      : "var(--amber-bg)",
                  }}
                >
                  {isPerson ? (
                    item.severity === "HIGH" ? (
                      <AlertTriangle size={18} color="var(--red)" />
                    ) : (
                      <User size={18} color="var(--blue)" />
                    )
                  ) : (
                    <Car size={18} color="var(--amber)" />
                  )}
                </div>
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 4,
                    }}
                  >
                    <span className={`badge ${item.severity?.toLowerCase()}`}>
                      {item.severity}
                    </span>
                    <span className={`badge ${item.source}`}>
                      {item.source}
                    </span>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: "0.92rem", color: "var(--text)" }}>
                    {item.headline}
                  </div>
                  {item.details && (
                    <div
                      style={{
                        fontSize: "0.82rem",
                        color: "var(--text-muted)",
                        marginTop: 2,
                      }}
                    >
                      {item.details}
                    </div>
                  )}
                  <div
                    style={{
                      fontSize: "0.78rem",
                      color: "var(--text-dim)",
                      marginTop: 4,
                      fontFamily: "JetBrains Mono, monospace",
                    }}
                  >
                    {item.camera_id} · {format(new Date(item.timestamp), "MMM d, yyyy · HH:mm:ss")}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

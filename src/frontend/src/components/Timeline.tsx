import { format } from "date-fns";
import { MapPin, Clock } from "lucide-react";
import type { EnrichedMatch } from "../types";

interface Props {
  matches: EnrichedMatch[];
}

export default function Timeline({ matches }: Props) {
  // Sort chronologically
  const sorted = [...matches].sort(
    (a, b) =>
      new Date(a.detected_at).getTime() - new Date(b.detected_at).getTime()
  );

  if (sorted.length === 0) {
    return (
      <div className="empty-state">
        <p>No sightings to display</p>
      </div>
    );
  }

  return (
    <div className="timeline">
      {sorted.map((m, idx) => (
        <div className="timeline-item" key={m.event_id}>
          <div className="timeline-time">
            <Clock size={12} style={{ marginRight: 4, verticalAlign: "middle" }} />
            {format(new Date(m.detected_at), "MMM d, yyyy · HH:mm:ss")}
          </div>
          <div className="timeline-camera">
            <MapPin size={13} style={{ marginRight: 4, verticalAlign: "middle" }} />
            #{idx + 1} · {m.camera_name}
          </div>
          <div className="cam-detail" style={{ fontSize: "0.8rem", color: "#9499b3", marginTop: 2 }}>
            {m.address || "Unknown location"} · {m.camera_id}
          </div>
          <div className="timeline-score" style={{ marginTop: 4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>{Math.round(m.similarity_score * 100)}% match</span>
              <div className="similarity-bar">
                <div
                  className="similarity-bar-fill"
                  style={{ width: `${m.similarity_score * 100}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

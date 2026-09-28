import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { EnrichedMatch } from "../types";

interface Props {
  matches: EnrichedMatch[];
  height?: string;
}

export default function PersonTrailMap({ matches, height = "500px" }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clean up previous map if any
    if (mapRef.current) {
      mapRef.current.remove();
      mapRef.current = null;
    }

    const map = L.map(containerRef.current, {
      zoomControl: true,
      attributionControl: true,
    }).setView([22.3, 72.0], 7);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    mapRef.current = map;

    const valid = matches.filter(
      (m) => m.latitude != null && m.longitude != null
    );

    if (valid.length === 0) return;

    // Sort chronologically for path sequence
    const sorted = [...valid].sort(
      (a, b) =>
        new Date(a.detected_at).getTime() - new Date(b.detected_at).getTime()
    );

    // Draw path line
    const coords = sorted.map(
      (m) => [m.latitude!, m.longitude!] as [number, number]
    );

    if (coords.length > 1) {
      L.polyline(coords, {
        color: "#6366f1",
        weight: 4,
        opacity: 0.85,
        dashArray: "8, 6",
      }).addTo(map);
    }

    // Numbered markers in chronological order
    sorted.forEach((m, idx) => {
      const icon = L.divIcon({
        className: "",
        html: `<div style="
          width: 28px; height: 28px;
          background: #6366f1;
          border: 2px solid #ffffff;
          border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          font-size: 12px; font-weight: 800; color: #ffffff;
          box-shadow: 0 0 12px rgba(99, 102, 241, 0.7), 0 3px 8px rgba(0,0,0,0.3);
          cursor: pointer;
        ">${idx + 1}</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });

      const time = new Date(m.detected_at).toLocaleTimeString();
      const marker = L.marker([m.latitude!, m.longitude!], { icon });

      marker.bindTooltip(
        `<div class="camera-tooltip-content">
          <div class="cam-name">#${idx + 1} · ${m.camera_name}</div>
          <div class="cam-detail">${m.address || "Unknown location"}</div>
          <div class="cam-detail">${time} · ${Math.round(m.similarity_score * 100)}% match</div>
        </div>`,
        { direction: "top", offset: [0, -14] }
      );

      marker.addTo(map);
    });

    // Fit bounds to show all markers
    const bounds = L.latLngBounds(coords);
    map.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [matches]);

  return (
    <div className="map-container" style={{ height }} ref={containerRef} />
  );
}

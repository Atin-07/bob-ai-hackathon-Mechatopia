import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Camera } from "../types";

// Fix Leaflet default icon asset paths in Vite
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const STATUS_COLORS: Record<string, string> = {
  online: "#10b981",
  offline: "#f43f5e",
  maintenance: "#f59e0b",
  inactive: "#94a3b8",
};

function normalizeStatus(raw: string | null | undefined): string {
  const s = (raw ?? "").trim().toLowerCase();
  if (["online", "live", "active", "up", "connected", "running"].includes(s)) return "online";
  if (s === "maintenance") return "maintenance";
  return "offline";
}

function createCameraIcon(status: string) {
  const color = STATUS_COLORS[status] || STATUS_COLORS.inactive;
  const pulse = status === "online" ? `<span class="cam-ring"></span>` : "";
  return L.divIcon({
    className: "",
    html: `<div class="cam-marker" style="--c:${color}">${pulse}<span class="cam-dot"></span></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

interface Props {
  cameras: Camera[];
  height?: string;
  selectedCameraId?: string | null;
  onCameraClick?: (cam: Camera) => void;
}

export default function CameraMap({
  cameras,
  height = "500px",
  selectedCameraId,
  onCameraClick,
}: Props) {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);

  // Initialize map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      zoomControl: true,
      attributionControl: true,
    }).setView([22.3, 72.0], 7);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    markersRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update markers when cameras change
  useEffect(() => {
    const map = mapRef.current;
    const markers = markersRef.current;
    if (!map || !markers) return;

    markers.clearLayers();

    const validCameras = cameras.filter(
      (c) => c.location?.latitude != null && c.location?.longitude != null
    );

    validCameras.forEach((cam) => {
      const status = normalizeStatus(cam.status);
      const marker = L.marker(
        [cam.location.latitude!, cam.location.longitude!],
        { icon: createCameraIcon(status), zIndexOffset: status === "online" ? 500 : 0 }
      );

      const tooltipHtml = `
        <div class="camera-tooltip-content">
          <div class="cam-name">${cam.name}</div>
          <div class="cam-detail">${cam.camera_id}</div>
          <div class="cam-status">
            <span class="status-dot ${status}"></span>
            <span style="text-transform: capitalize;">${status === "online" ? "online · live" : status}</span>
          </div>
          <div class="cam-detail">${cam.location.address || "—"}</div>
          <div class="cam-detail">${cam.department || ""} ${cam.district ? `· ${cam.district}` : ""}</div>
          <div class="cam-detail">${cam.camera_type || ""} ${cam.properties?.codec ? `· ${String(cam.properties.codec)}` : ""} ${cam.properties?.width ? `${String(cam.properties.width)}×${String(cam.properties.height)}` : ""}</div>
        </div>
      `;

      marker.bindTooltip(tooltipHtml, {
        direction: "top",
        offset: [0, -10],
        sticky: false,
      });

      if (onCameraClick) {
        marker.on("click", () => onCameraClick(cam));
      }

      markers.addLayer(marker);
    });

    if (validCameras.length > 0) {
      const bounds = L.latLngBounds(
        validCameras.map((c) => [c.location.latitude!, c.location.longitude!])
      );
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
    }
  }, [cameras, onCameraClick]);

  // Pan to selected camera
  useEffect(() => {
    if (!selectedCameraId || !mapRef.current) return;
    const cam = cameras.find((c) => c.camera_id === selectedCameraId);
    if (cam?.location.latitude != null && cam.location.longitude != null) {
      mapRef.current.setView(
        [cam.location.latitude, cam.location.longitude],
        14,
        { animate: true }
      );
    }
  }, [selectedCameraId, cameras]);

  const counts = { online: 0, offline: 0, maintenance: 0 } as Record<string, number>;
  cameras.forEach((c) => {
    counts[normalizeStatus(c.status)] += 1;
  });

  return (
    <div style={{ position: "relative" }}>
      <div className="map-container" style={{ height }} ref={containerRef} />
      <div
        style={{
          position: "absolute",
          bottom: 28,
          left: 12,
          zIndex: 1000,
          background: "rgba(15,23,42,0.85)",
          color: "#e2e8f0",
          padding: "6px 10px",
          borderRadius: 8,
          fontSize: "0.72rem",
          display: "flex",
          gap: 12,
        }}
      >
        {(["online", "offline", "maintenance"] as const).map((s) => (
          <span key={s} style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                background: STATUS_COLORS[s],
                display: "inline-block",
              }}
            />
            {s === "online" ? "Live" : s[0].toUpperCase() + s.slice(1)} ({counts[s]})
          </span>
        ))}
      </div>
    </div>
  );
}
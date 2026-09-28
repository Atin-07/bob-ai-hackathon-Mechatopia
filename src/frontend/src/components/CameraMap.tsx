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

function createCameraIcon(status: string) {
  const color = STATUS_COLORS[status] || STATUS_COLORS.inactive;
  return L.divIcon({
    className: "",
    html: `<div style="
      width: 18px; height: 18px;
      background: ${color};
      border: 3px solid #ffffff;
      border-radius: 50%;
      box-shadow: 0 0 10px ${color}cc, 0 2px 5px rgba(0,0,0,0.3);
      cursor: pointer;
    "></div>`,
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
      (c) => c.location.latitude != null && c.location.longitude != null
    );

    validCameras.forEach((cam) => {
      const marker = L.marker(
        [cam.location.latitude!, cam.location.longitude!],
        { icon: createCameraIcon(cam.status) }
      );

      // Tooltip on hover with camera details
      const tooltipHtml = `
        <div class="camera-tooltip-content">
          <div class="cam-name">${cam.name}</div>
          <div class="cam-detail">${cam.camera_id}</div>
          <div class="cam-status">
            <span class="status-dot ${cam.status}"></span>
            <span style="text-transform: capitalize;">${cam.status}</span>
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

    // Fit bounds if cameras exist
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

  return (
    <div
      className="map-container"
      style={{ height }}
      ref={containerRef}
    />
  );
}

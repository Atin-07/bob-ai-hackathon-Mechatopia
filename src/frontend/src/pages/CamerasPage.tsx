import { useEffect, useState } from "react";
import {
  Search,
  RefreshCw,
  Download,
  Filter,
  Layers,
} from "lucide-react";
import { fetchCameras } from "../api";
import CameraMap from "../components/CameraMap";
import type { Camera } from "../types";
import { CORE_API } from "../config";

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [filtered, setFiltered] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [districtFilter, setDistrictFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchCameras();
      setCameras(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // Client-side filtering
  useEffect(() => {
    let result = cameras;
    if (statusFilter !== "all") {
      result = result.filter((c) => c.status === statusFilter);
    }
    if (districtFilter !== "all") {
      result = result.filter((c) => c.district === districtFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (c) =>
          c.camera_id.toLowerCase().includes(q) ||
          c.name.toLowerCase().includes(q) ||
          c.location.address?.toLowerCase().includes(q)
      );
    }
    setFiltered(result);
  }, [cameras, statusFilter, districtFilter, search]);

  const districts = [...new Set(cameras.map((c) => c.district).filter(Boolean))];

  if (loading) return <div className="spinner" />;

  const onlineCount = cameras.filter((c) => c.status === "online").length;

  return (
    <div>
      <div className="page-header">
        <h1>Camera Directory &amp; GIS Map</h1>
        <p>
          {cameras.length} cameras registered · <span style={{ color: "var(--green)", fontWeight: 600 }}>{onlineCount} online</span> across Gujarat
        </p>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 260, maxWidth: 360 }}>
          <Search size={16} color="var(--text-dim)" />
          <input
            type="search"
            placeholder="Search by ID, name, or address…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: "100%" }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Filter size={15} color="var(--text-dim)" />
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All statuses</option>
            <option value="online">Online</option>
            <option value="offline">Offline</option>
            <option value="maintenance">Maintenance</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Layers size={15} color="var(--text-dim)" />
          <select value={districtFilter} onChange={(e) => setDistrictFilter(e.target.value)}>
            <option value="all">All districts</option>
            {districts.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>

        <div style={{ marginLeft: "auto", display: "flex", gap: 10 }}>
          <button className="btn btn-outline" onClick={load} title="Reload cameras">
            <RefreshCw size={14} /> Refresh
          </button>
          <a
            className="btn btn-outline"
            href={`${CORE_API}/cameras/export/csv`}
            target="_blank"
            rel="noreferrer"
          >
            <Download size={14} /> Export CSV
          </a>
        </div>
      </div>

      {/* Interactive Map */}
      <div style={{ marginBottom: 24 }}>
        <CameraMap
          cameras={filtered}
          height="450px"
          selectedCameraId={selectedId}
          onCameraClick={(cam) => setSelectedId(cam.camera_id)}
        />
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 80 }}>Status</th>
                <th>Camera ID</th>
                <th>Name</th>
                <th>Location / Address</th>
                <th>District</th>
                <th>Department</th>
                <th>Type</th>
                <th>Stream / Specs</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((cam) => (
                <tr
                  key={cam.camera_id}
                  style={{
                    cursor: "pointer",
                    background:
                      selectedId === cam.camera_id
                        ? "var(--bg-card-hover)"
                        : undefined,
                  }}
                  onClick={() => setSelectedId(cam.camera_id)}
                >
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className={`status-dot ${cam.status}`} />
                      <span style={{ fontSize: "0.75rem", textTransform: "capitalize", color: "var(--text-muted)" }}>
                        {cam.status}
                      </span>
                    </div>
                  </td>
                  <td style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "0.82rem", fontWeight: 600 }}>
                    {cam.camera_id}
                  </td>
                  <td style={{ fontWeight: 600 }}>{cam.name}</td>
                  <td style={{ color: "var(--text-muted)" }}>{cam.location.address || "—"}</td>
                  <td>{cam.district || "—"}</td>
                  <td>{cam.department || "—"}</td>
                  <td>
                    <span className="badge" style={{ background: "var(--bg-subtle)", color: "var(--text)" }}>
                      {cam.camera_type}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--text-dim)", fontFamily: "JetBrains Mono, monospace" }}>
                    {cam.properties?.codec ? String(cam.properties.codec) : "H264"} {cam.properties?.width ? `· ${String(cam.properties.width)}×${String(cam.properties.height)}` : ""}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={8} className="empty-state">
                    No cameras match the current filters
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

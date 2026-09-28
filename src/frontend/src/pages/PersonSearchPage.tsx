import { useState, useCallback } from "react";
import { Search, MapPin, Clock, Filter, Users } from "lucide-react";
import { searchPerson, fetchCameras } from "../api";
import ImageUpload from "../components/ImageUpload";
import PersonTrailMap from "../components/PersonTrailMap";
import Timeline from "../components/Timeline";
import type { Camera, EnrichedMatch, PersonMatch } from "../types";

export default function PersonSearchPage() {
  const [file, setFile] = useState<File | null>(null);
  const [matches, setMatches] = useState<EnrichedMatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  // Filters
  const [minSimilarity, setMinSimilarity] = useState(0.5);
  const [cameraFilter, setCameraFilter] = useState("all");
  const [topK, setTopK] = useState(50);

  const handleSearch = useCallback(async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setSearched(true);

    try {
      // Query search and cameras in parallel
      const [cameras, result] = await Promise.all([
        fetchCameras().catch(() => []),
        searchPerson(file, topK),
      ]);

      // Build camera lookup map
      const camMap = new Map<string, Camera>();
      cameras.forEach((c) => camMap.set(c.camera_id, c));

      // Enrich sightings with geolocations and camera names
      const enriched: EnrichedMatch[] = (result.matches || []).map(
        (m: PersonMatch) => {
          const cam = camMap.get(m.camera_id);
          return {
            ...m,
            camera_name: cam?.name ?? m.camera_id,
            latitude: cam?.location.latitude ?? null,
            longitude: cam?.location.longitude ?? null,
            address: cam?.location.address ?? "",
          };
        }
      );

      setMatches(enriched);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setMatches([]);
    } finally {
      setLoading(false);
    }
  }, [file, topK]);

  // Apply client-side filters
  const filtered = matches.filter((m) => {
    if (m.similarity_score < minSimilarity) return false;
    if (cameraFilter !== "all" && m.camera_id !== cameraFilter) return false;
    return true;
  });

  // Unique cameras for the filter dropdown
  const cameraIds = [...new Set(matches.map((m) => m.camera_id))];

  // Group sightings by camera
  const groupedByCamera = filtered.reduce<Record<string, EnrichedMatch[]>>(
    (acc, m) => {
      (acc[m.camera_id] = acc[m.camera_id] || []).push(m);
      return acc;
    },
    {}
  );

  return (
    <div>
      <div className="page-header">
        <h1>Person Search</h1>
        <p>Upload a photo to find all sightings across cameras</p>
      </div>

      <div className="search-layout">
        {/* Left panel – upload & filters */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card">
            <h3 className="card-title">
              <Search size={16} /> Upload Photo
            </h3>
            <ImageUpload
              onFileSelected={(f) => setFile(f)}
              disabled={loading}
            />
            <div style={{ marginTop: 12 }}>
              <label style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>
                Max results (top_k)
              </label>
              <input
                type="number"
                value={topK}
                min={1}
                max={100}
                onChange={(e) => setTopK(Number(e.target.value))}
                style={{ width: "100%", marginTop: 4 }}
              />
            </div>
            <button
              className="btn btn-primary"
              style={{ width: "100%", marginTop: 12, justifyContent: "center" }}
              onClick={handleSearch}
              disabled={!file || loading}
            >
              {loading ? "Searching…" : "Search"}
            </button>
          </div>

          {/* Filters – only visible after search */}
          {searched && matches.length > 0 && (
            <div className="card">
              <h3 className="card-title">
                <Filter size={16} /> Filters
              </h3>
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>
                  Min similarity: {Math.round(minSimilarity * 100)}%
                </label>
                <br />
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={minSimilarity * 100}
                  onChange={(e) => setMinSimilarity(Number(e.target.value) / 100)}
                  style={{ width: "100%", marginTop: 6 }}
                />
              </div>
              <div>
                <label style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>
                  Camera
                </label>
                <select
                  value={cameraFilter}
                  onChange={(e) => setCameraFilter(e.target.value)}
                  style={{ width: "100%", marginTop: 4 }}
                >
                  <option value="all">All cameras</option>
                  {cameraIds.map((id) => (
                    <option key={id} value={id}>{id}</option>
                  ))}
                </select>
              </div>
              <div style={{ marginTop: 12, fontSize: "0.8rem", color: "var(--text-dim)" }}>
                Showing {filtered.length} of {matches.length} results
              </div>
            </div>
          )}

          {/* Grouped by camera */}
          {searched && Object.keys(groupedByCamera).length > 0 && (
            <div className="card">
              <h3 className="card-title">
                <Users size={16} /> By Camera
              </h3>
              {Object.entries(groupedByCamera).map(([camId, items]) => (
                <div
                  key={camId}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "6px 0",
                    borderBottom: "1px solid var(--border)",
                    fontSize: "0.85rem",
                  }}
                >
                  <span>
                    <MapPin size={12} style={{ marginRight: 4, verticalAlign: "middle" }} />
                    {items[0].camera_name}
                  </span>
                  <span style={{ color: "var(--accent-light)", fontWeight: 600 }}>
                    {items.length} sighting{items.length > 1 ? "s" : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right panel – map + timeline */}
        <div className="search-results-area">
          {error && (
            <div className="card" style={{ borderLeftColor: "var(--red)", borderLeftWidth: 3 }}>
              <p style={{ color: "var(--red)" }}>{error}</p>
            </div>
          )}

          {!searched && (
            <div className="card empty-state" style={{ padding: "80px 20px" }}>
              <Search size={48} style={{ opacity: 0.3 }} />
              <p style={{ marginTop: 12 }}>Upload a photo of a person to search across all cameras</p>
            </div>
          )}

          {searched && filtered.length === 0 && !loading && (
            <div className="card empty-state" style={{ padding: "80px 20px" }}>
              <Users size={48} style={{ opacity: 0.3 }} />
              <p style={{ marginTop: 12 }}>No sightings found. Try a different photo or lower the similarity threshold.</p>
            </div>
          )}

          {loading && <div className="spinner" />}

          {filtered.length > 0 && (
            <>
              {/* Map */}
              <div className="card">
                <h3 className="card-title">
                  <MapPin size={16} /> Person Trail Map
                </h3>
                <PersonTrailMap matches={filtered} height="420px" />
              </div>

              {/* Timeline */}
              <div className="card">
                <h3 className="card-title">
                  <Clock size={16} /> Detection Timeline
                </h3>
                <Timeline matches={filtered} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

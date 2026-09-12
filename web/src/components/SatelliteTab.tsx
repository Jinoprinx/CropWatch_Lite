"use client";

import React, { useEffect, useRef, useState } from "react";
import { MapPin, RefreshCw, AlertTriangle, Crosshair } from "@/components/Icons";

interface SatelliteTabProps {
  onSelectScoutHotspot?: (lat: number, lon: number) => void;
}

export const SatelliteTab: React.FC<SatelliteTabProps> = ({ onSelectScoutHotspot }) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const polygonLayerRef = useRef<any>(null);
  const markersLayerRef = useRef<any>(null);
  const mapReadyRef = useRef(false);

  const [fields, setFields] = useState<any[]>([]);
  const [selectedFieldId, setSelectedFieldId] = useState("field_corn_01");
  const [activeLayer, setActiveLayer] = useState<"ndvi" | "ndre" | "ndwi" | "rgb">("ndvi");
  const [loading, setLoading] = useState(false);

  const [analysis, setAnalysis] = useState<any>({
    summary_indices: { mean_ndvi: 0.78, mean_ndre: 0.54, mean_ndwi: 0.42, mean_savi: 0.65 },
    anomaly_analysis: {
      status: "success",
      risk_assessment: "Moderate Caution",
      anomalous_area_pct: 4.2,
      anomalous_area_ha: 1.44,
      hotspots: []
    },
    layers: { true_color: "", ndvi_heatmap: "", ndre_heatmap: "", ndwi_heatmap: "" }
  });

  useEffect(() => {
    let isMounted = true;
    let initTimer: ReturnType<typeof setTimeout>;

    async function loadLeaflet(): Promise<any> {
      if ((window as any).L) return (window as any).L;
      return new Promise((resolve) => {
        const script = document.createElement("script");
        script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
        script.onload = () => resolve((window as any).L);
        document.head.appendChild(script);
      });
    }

    async function initMapAndData() {
      if (typeof window === "undefined" || !mapContainerRef.current) return;

      const L = await loadLeaflet();
      if (!L || !isMounted) return;

      // Only initialize map once
      if (!mapInstanceRef.current && !(mapContainerRef.current as any)._leaflet_id) {
        const map = L.map(mapContainerRef.current, {
          zoomControl: true,
          attributionControl: false
          // NO preferCanvas — use default SVG renderer
        }).setView([42.0215, -93.646], 15);

        L.tileLayer(
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          { maxZoom: 19 }
        ).addTo(map);

        polygonLayerRef.current = L.layerGroup().addTo(map);
        markersLayerRef.current = L.layerGroup().addTo(map);
        mapInstanceRef.current = map;
      }

      // Wait for the browser to paint the map container and compute its pixel dimensions
      // before any fitBounds / layer operations. 600ms is safe for all machines.
      initTimer = setTimeout(async () => {
        if (!isMounted || !mapInstanceRef.current) return;

        // Force Leaflet to recalculate container dimensions
        mapInstanceRef.current.invalidateSize(true);

        // Now fetch fields and draw
        let fieldsToUse: any[] = [];
        try {
          const res = await fetch("http://localhost:8000/api/fields");
          const data = await res.json();
          if (isMounted && data.features && data.features.length > 0) {
            fieldsToUse = data.features;
          }
        } catch {
          fieldsToUse = [
            {
              type: "Feature",
              id: "field_corn_01",
              properties: { name: "Oakridge Corn Sector Alpha", crop: "corn", area_ha: 34.2 },
              geometry: {
                type: "Polygon",
                coordinates: [[
                  [-93.650, 42.025], [-93.642, 42.025],
                  [-93.642, 42.018], [-93.650, 42.018],
                  [-93.650, 42.025]
                ]]
              }
            }
          ];
        }

        if (isMounted && fieldsToUse.length > 0) {
          setFields(fieldsToUse);
          mapReadyRef.current = true;
          drawFieldAndScan(fieldsToUse, "field_corn_01");
        }
      }, 600);
    }

    initMapAndData();

    return () => {
      isMounted = false;
      clearTimeout(initTimer);
      if (mapInstanceRef.current) {
        try { mapInstanceRef.current.remove(); } catch { /* ignore */ }
        mapInstanceRef.current = null;
        mapReadyRef.current = false;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const drawFieldAndScan = (fieldsList: any[], fieldId: string) => {
    const L = (window as any).L;
    const map = mapInstanceRef.current;
    if (!map || !polygonLayerRef.current || !L) return;

    polygonLayerRef.current.clearLayers();
    const field = fieldsList.find(f => f.id === fieldId) || fieldsList[0];
    if (!field || !field.geometry) return;

    try {
      // L.geoJSON natively understands GeoJSON Feature objects
      const geoLayer = L.geoJSON(field, {
        style: {
          color: "#10b981",
          weight: 3,
          fillColor: "#10b981",
          fillOpacity: 0.16,
          dashArray: "6, 4"
        },
        onEachFeature: (feature: any, layer: any) => {
          const p = feature.properties || {};
          layer.bindPopup(
            `<strong>${p.name || "Field"}</strong><br>Crop: ${p.crop || "—"}<br>Area: ${p.area_ha || 0} ha`
          );
        }
      }).addTo(polygonLayerRef.current);

      // Compute bounds from raw GeoJSON coordinates — validate each pair first
      const rawCoords: number[][] = field.geometry?.coordinates?.[0] ?? [];
      if (rawCoords.length >= 3) {
        // Filter out any malformed [lon, lat] pairs before constructing LatLng objects
        const validLatLngs = rawCoords
          .filter((c: number[]) =>
            Array.isArray(c) &&
            c.length >= 2 &&
            isFinite(c[0]) && !isNaN(c[0]) &&
            isFinite(c[1]) && !isNaN(c[1])
          )
          .map((c: number[]) => L.latLng(c[1], c[0]));

        if (validLatLngs.length >= 2) {
          const bounds = L.latLngBounds(validLatLngs);
          if (bounds.isValid()) {
            // invalidateSize ensures the map container has correct pixel dimensions,
            // then defer fitBounds to the next animation frame so the browser has painted.
            map.invalidateSize(false);
            requestAnimationFrame(() => {
              try {
                map.fitBounds(bounds, { padding: [35, 35] });
              } catch {
                // fitBounds can still throw if the map was destroyed between frames
              }
            });
          }
        }
      }

      void geoLayer; // Layer added to map — bounds handled separately above
    } catch (err) {
      console.warn("Leaflet polygon error:", err);
    }

    runScan(field);
  };

  const placeHotspotMarkers = (hotspots: any[]) => {
    const L = (window as any).L;
    const map = mapInstanceRef.current;
    if (!L || !map || !markersLayerRef.current) return;

    markersLayerRef.current.clearLayers();

    hotspots.forEach((h: any) => {
      const lat = parseFloat(h.latitude);
      const lon = parseFloat(h.longitude);
      if (isNaN(lat) || isNaN(lon) || !isFinite(lat) || !isFinite(lon)) return;

      const isHigh = h.severity === "high";

      // HTML DivIcon — never touches Leaflet's SVG/Canvas path renderer
      const icon = L.divIcon({
        className: "",
        html: `<div class="hotspot-pulse-container">
          <div class="hotspot-pulse-ring ${isHigh ? "red" : "amber"}"></div>
          <div class="hotspot-pulse-badge ${isHigh ? "red" : "amber"}">${h.hotspot_id ?? 1}</div>
        </div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
        popupAnchor: [0, -14]
      });

      const marker = L.marker([lat, lon], { icon });
      const area = parseFloat(h.area_m2) || 0;
      marker.bindPopup(
        `<strong>Hotspot #${h.hotspot_id ?? 1} · ${(h.severity || "").toUpperCase()}</strong>` +
        `<br>${h.probable_cause || "Anomaly Cluster"}` +
        `<br>Area: ${area} m²` +
        `<br><em>${h.recommended_action || "Scout & Sample"}</em>`
      );
      marker.addTo(markersLayerRef.current);
    });
  };

  const runScan = async (targetField?: any) => {
    setLoading(true);
    const field = targetField || fields.find(f => f.id === selectedFieldId) || fields[0];
    const coords = field?.geometry?.coordinates?.[0] ?? [
      [-93.65, 42.02], [-93.64, 42.02], [-93.64, 42.01], [-93.65, 42.01]
    ];
    const lons = coords.map((c: number[]) => c[0]);
    const lats = coords.map((c: number[]) => c[1]);
    const bbox = [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];

    try {
      const res = await fetch("http://localhost:8000/api/satellite/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bbox,
          crop_type: field?.properties?.crop ?? "corn",
          growth_stage: "peak_vegetative",
          origin_lat: (bbox[1] + bbox[3]) / 2,
          origin_lon: (bbox[0] + bbox[2]) / 2
        })
      });
      const data = await res.json();
      setAnalysis(data);

      if (data.anomaly_analysis?.hotspots?.length) {
        placeHotspotMarkers(data.anomaly_analysis.hotspots);
      }
    } catch (e) {
      console.error("Satellite scan failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    setSelectedFieldId(id);
    if (mapReadyRef.current) drawFieldAndScan(fields, id);
  };

  const getOverlayImageSrc = () => {
    if (!analysis?.layers) return "";
    if (activeLayer === "ndvi") return analysis.layers.ndvi_heatmap;
    if (activeLayer === "ndre") return analysis.layers.ndre_heatmap;
    if (activeLayer === "ndwi") return analysis.layers.ndwi_heatmap;
    return analysis.layers.true_color;
  };

  return (
    <div className="grid-layout-2col">
      <div className="card map-card">
        <div className="card-header">
          <div className="card-title">
            <MapPin size={18} color="#10b981" /> Farm Boundary &amp; Multi-Spectral Surveillance
          </div>
          <div className="field-selector-group">
            <label htmlFor="field-select" style={{ fontSize: "12px", color: "var(--text-muted)", marginRight: "8px" }}>Field:</label>
            <select id="field-select" className="form-select" value={selectedFieldId} onChange={handleFieldChange}>
              {fields.map(f => (
                <option key={f.id} value={f.id}>{f.properties.name} ({f.properties.area_ha} ha)</option>
              ))}
            </select>
          </div>
        </div>

        <div className="map-controls-bar">
          <span className="control-label">Spectral Layer:</span>
          <div className="btn-group">
            {(["ndvi", "ndre", "ndwi", "rgb"] as const).map(layer => (
              <button
                key={layer}
                className={`btn-layer ${activeLayer === layer ? "active" : ""}`}
                onClick={() => setActiveLayer(layer)}
              >
                {layer === "ndvi" ? "NDVI (Biomass)"
                  : layer === "ndre" ? "NDRE (Red-Edge)"
                  : layer === "ndwi" ? "NDWI (Moisture)"
                  : "True Color RGB"}
              </button>
            ))}
          </div>
          <button className="btn btn-sm btn-success ml-auto" onClick={() => runScan()} disabled={loading}>
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            {loading ? "Scanning..." : "Ingest & Scan"}
          </button>
        </div>

        <div className="map-wrapper">
          <div ref={mapContainerRef} id="satellite-map" style={{ width: "100%", height: "100%" }} />
          {getOverlayImageSrc() && (
            <div className="raster-overlay">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={getOverlayImageSrc()} alt="Spectral Raster Layer" />
              <div className="legend-box">
                <span>{activeLayer.toUpperCase()} Heatmap:</span>
                <div className="color-ramp" />
                <div className="legend-values">
                  <span>0.1 (Stress)</span><span>0.5</span><span>0.9 (Lush)</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card-column">
        <div className="card">
          <div className="card-header">
            <div className="card-title">Field Spectral Vigor Indices</div>
            <span className="badge badge-emerald">Peak Vegetative</span>
          </div>
          <div className="kpi-grid">
            {[
              { label: "Mean NDVI", val: analysis.summary_indices?.mean_ndvi, color: "emerald", sub: "Biomass Interception" },
              { label: "Red-Edge NDRE", val: analysis.summary_indices?.mean_ndre, color: "cyan", sub: "Chlorophyll Density" },
              { label: "Water Index (NDWI)", val: analysis.summary_indices?.mean_ndwi, color: "blue", sub: "Canopy Hydration" },
              { label: "Soil Adjusted (SAVI)", val: analysis.summary_indices?.mean_savi, color: "amber", sub: "Soil Neutralized" }
            ].map(({ label, val, color, sub }) => (
              <div key={label} className="kpi-card">
                <div className="kpi-label">{label}</div>
                <div className={`kpi-value ${color}`}>{val?.toFixed(2) ?? "—"}</div>
                <div className="kpi-sub">{sub}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <AlertTriangle size={16} color="#f59e0b" /> Pre-Symptomatic Hotspots
            </div>
            <span className={`badge ${(analysis.anomaly_analysis?.anomalous_area_pct ?? 0) > 6 ? "badge-red" : "badge-amber"}`}>
              {analysis.anomaly_analysis?.risk_assessment ?? "Moderate Caution"} ({analysis.anomaly_analysis?.anomalous_area_pct ?? 4.2}% Area)
            </span>
          </div>
          <p className="card-desc">
            Spatial z-score and Red-Edge deficit detection isolated statistically anomalous chlorophyll-collapse clusters.
          </p>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr><th>ID</th><th>GPS</th><th>Area</th><th>Cause</th><th>Scout</th></tr>
              </thead>
              <tbody>
                {(analysis.anomaly_analysis?.hotspots?.length ?? 0) > 0 ? (
                  analysis.anomaly_analysis.hotspots.map((h: any) => (
                    <tr key={h.hotspot_id}>
                      <td><strong>#{h.hotspot_id}</strong></td>
                      <td><span style={{ fontFamily: "monospace" }}>{h.latitude.toFixed(4)}, {h.longitude.toFixed(4)}</span></td>
                      <td>{h.area_m2} m²</td>
                      <td><span className={`badge ${h.severity === "high" ? "badge-red" : "badge-amber"}`}>{h.probable_cause}</span></td>
                      <td>
                        <button
                          className="btn btn-xs btn-outline"
                          onClick={() => {
                            const lat = parseFloat(h.latitude);
                            const lon = parseFloat(h.longitude);
                            if (!isNaN(lat) && !isNaN(lon) && mapInstanceRef.current) {
                              try { mapInstanceRef.current.setView([lat, lon], 17); } catch { /* ignore */ }
                            }
                            if (onSelectScoutHotspot && !isNaN(lat) && !isNaN(lon)) {
                              onSelectScoutHotspot(lat, lon);
                            }
                          }}
                        >
                          <Crosshair size={11} /> Scout
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", color: "var(--emerald-primary)" }}>
                      ✓ No anomaly clusters detected — canopy vigor homogeneous.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

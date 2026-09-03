"use client";

import React, { useState, useEffect } from "react";
import { Compass, Calculator, Satellite, Camera, Images } from "@/components/Icons";

export const FlightPlannerTab: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [camera, setCamera] = useState("dji_mavic_3e");
  const [area, setArea] = useState(34.2);
  const [altitude, setAltitude] = useState(65);
  const [fwdOverlap, setFwdOverlap] = useState(75);
  const [sideOverlap, setSideOverlap] = useState(70);
  const [speed, setSpeed] = useState(7.5);

  const [planResult, setPlanResult] = useState<any>({
    camera_model: "DJI Mavic 3 Enterprise (RGB)",
    flight_altitude_m: 65,
    gsd_cm_per_pixel: 1.78,
    ground_footprint_m: "91.3m x 68.6m",
    flight_lines_count: 24,
    total_flight_distance_km: 14.2,
    estimated_flight_time_minutes: 32.4,
    batteries_needed: 2,
    total_images_estimated: 480,
    recommended_shutter_speed: "1/840s or faster",
    survey_feasibility: "Optimal High-Precision Survey"
  });

  useEffect(() => {
    calculatePlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const calculatePlan = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/drone/flight-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          field_area_ha: area,
          camera_type: camera,
          flight_altitude_m: altitude,
          forward_overlap_pct: fwdOverlap,
          side_overlap_pct: sideOverlap,
          flight_speed_m_s: speed,
          battery_flight_time_min: 24.0
        })
      });
      const data = await res.json();
      setPlanResult(data);
    } catch (err) {
      console.error("Flight plan calculation failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid-layout-2col">
      {/* Left: Input Parameters Form */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Compass size={18} color="#06b6d4" /> UAV Photogrammetry &amp; Optics Physics
          </div>
          <button className="btn btn-sm btn-primary" onClick={calculatePlan} disabled={loading}>
            <Calculator size={13} /> {loading ? "Computing..." : "Calculate Flight Path"}
          </button>
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label>Camera Sensor Payload</label>
            <select className="form-select" value={camera} onChange={e => setCamera(e.target.value)}>
              <option value="dji_mavic_3e">DJI Mavic 3 Enterprise 4/3&quot; RGB</option>
              <option value="dji_mini_4_pro">DJI Mini 4 Pro / Consumer 1/1.3&quot; RGB</option>
              <option value="micasense_rededge_p">MicaSense RedEdge-P Multispectral</option>
            </select>
          </div>

          <div className="form-group">
            <label>Field Survey Area (Hectares)</label>
            <input
              type="number"
              className="form-input"
              value={area}
              step="0.5"
              onChange={e => setArea(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Flight Altitude Above Ground (Meters)</label>
            <input
              type="number"
              className="form-input"
              value={altitude}
              step="5"
              min="20"
              max="150"
              onChange={e => setAltitude(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Forward Overlap (%)</label>
            <input
              type="number"
              className="form-input"
              value={fwdOverlap}
              step="5"
              onChange={e => setFwdOverlap(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Side Overlap (%)</label>
            <input
              type="number"
              className="form-input"
              value={sideOverlap}
              step="5"
              onChange={e => setSideOverlap(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Flight Speed (m/s)</label>
            <input
              type="number"
              className="form-input"
              value={speed}
              step="0.5"
              onChange={e => setSpeed(parseFloat(e.target.value))}
            />
          </div>
        </div>
      </div>

      {/* Right: Kinematics & Logistics Results */}
      <div className="card-column">
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Satellite size={18} color="#10b981" /> Mission Kinematics &amp; Battery Logistics
            </div>
          </div>

          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">Ground Sampling (GSD)</div>
              <div className="kpi-value cyan">{planResult.gsd_cm_per_pixel} cm/px</div>
              <div className="kpi-sub">Sub-Canopy Precision</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Flight Duration</div>
              <div className="kpi-value emerald">{planResult.estimated_flight_time_minutes} min</div>
              <div className="kpi-sub">Total Line Time</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Flight Lines</div>
              <div className="kpi-value amber">{planResult.flight_lines_count} passes</div>
              <div className="kpi-sub">Grid Geometry</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Batteries Required</div>
              <div className="kpi-value purple">{planResult.batteries_needed} packs</div>
              <div className="kpi-sub">24m nominal endurance</div>
            </div>
          </div>

          <div className="flight-notes-box">
            <div className="flight-note-item">
              <Camera size={16} />
              <span>
                Max Shutter Speed to prevent motion blur: <strong>{planResult.recommended_shutter_speed}</strong>
              </span>
            </div>
            <div className="flight-note-item">
              <Images size={16} />
              <span>
                Total images captured: <strong>{planResult.total_images_estimated} photos</strong> (approx. {planResult.total_flight_distance_km} km path)
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

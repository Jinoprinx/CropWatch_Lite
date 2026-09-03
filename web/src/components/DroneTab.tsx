"use client";

import React, { useState, useEffect, useRef } from "react";
import { UploadCloud, ImageIcon, Sparkles, Layers } from "@/components/Icons";

export const DroneTab: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [sampleDroneTile, setSampleDroneTile] = useState<string>("");

  const [droneData, setDroneData] = useState<any>({
    resolution_px: "640x640",
    gsd_cm_px: 2.5,
    flight_altitude_m: 60.0,
    total_scanned_area_m2: 256.0,
    canopy_coverage_percentage: 82.4,
    healthy_canopy_pct: 91.8,
    stressed_infected_canopy_pct: 8.2,
    precision_spray_advisory: {
      conventional_spray_liters: 510.0,
      cropwatch_precision_spray_liters: 130.2,
      chemical_and_cost_savings_pct: 74.5,
      spray_recommendation: "Variable-rate spot treatment reduces chemical application by 74.5%."
    },
    original_b64: "",
    heatmap_base64: ""
  });

  useEffect(() => {
    async function fetchSample() {
      try {
        const res = await fetch("http://localhost:8000/api/sample-assets");
        const data = await res.json();
        if (data.drone_tiles && data.drone_tiles.length > 0) {
          setSampleDroneTile(data.drone_tiles[0].base64);
          analyzeDroneImage(data.drone_tiles[0].base64);
        }
      } catch (err) {
        console.error("Failed to load sample drone tile:", err);
      }
    }
    fetchSample();
  }, []);

  const analyzeDroneImage = async (b64OrFile: string | File) => {
    setLoading(true);
    try {
      const form = new FormData();
      if (typeof b64OrFile === "string") {
        form.append("image_base64", b64OrFile);
      } else {
        form.append("file", b64OrFile);
      }
      form.append("gsd_cm", "2.5");
      form.append("altitude_m", "60.0");

      const res = await fetch("http://localhost:8000/api/drone/analyze", {
        method: "POST",
        body: form
      });
      const data = await res.json();
      setDroneData({
        ...data,
        original_b64: typeof b64OrFile === "string" ? b64OrFile : URL.createObjectURL(b64OrFile)
      });
    } catch (e) {
      console.error("Drone analysis failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      analyzeDroneImage(e.target.files[0]);
    }
  };

  return (
    <div className="grid-layout-2col">
      {/* Left: Upload & Heatmap Comparison */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Layers size={18} color="#06b6d4" /> Sub-Meter Visible Photogrammetry (VARI / GLI)
          </div>
          <span className="badge badge-cyan">Low-Cost RGB Solution</span>
        </div>

        <div className="drone-upload-box" onClick={() => fileInputRef.current?.click()}>
          <UploadCloud size={32} color="#10b981" className="upload-icon" />
          <div className="upload-title">{loading ? "Processing Orthomosaic..." : "Drop High-Res Drone Ortho Tile or Click to Upload"}</div>
          <div className="upload-sub">Supports 4K/20MP aerial JPGs from standard DJI Mini / Air / Mavic drones</div>
          <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileUpload} />
        </div>

        {sampleDroneTile && (
          <div className="sample-picker">
            <span>Or load pre-calibrated sample:</span>
            <button className="btn btn-xs btn-outline" onClick={() => analyzeDroneImage(sampleDroneTile)}>
              <ImageIcon size={12} /> Sample 20MP Crop Row Ortho Tile
            </button>
          </div>
        )}

        <div className="drone-image-comparison">
          <div className="image-box">
            <div className="image-tag">Original Drone RGB (2.5 cm/px GSD)</div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={droneData.original_b64 || "/placeholder.png"} alt="Drone Original" />
          </div>
          <div className="image-box">
            <div className="image-tag">VARI Canopy Health Heatmap</div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={droneData.heatmap_base64 || "/placeholder.png"} alt="Drone VARI Heatmap" />
          </div>
        </div>
      </div>

      {/* Right: Canopy Stats & Variable-Rate Spraying */}
      <div className="card-column">
        {/* Canopy Metrics Card */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Canopy Fraction &amp; Vigor Quantification</div>
          </div>

          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">Canopy Cover %</div>
              <div className="kpi-value emerald">{droneData.canopy_coverage_percentage}%</div>
              <div className="kpi-sub">Green Ground Fraction</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Healthy Foliage %</div>
              <div className="kpi-value cyan">{droneData.healthy_canopy_pct}%</div>
              <div className="kpi-sub">VARI &gt; 0.12</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Stressed / Blight Area</div>
              <div className="kpi-value amber">{droneData.stressed_infected_canopy_pct}%</div>
              <div className="kpi-sub">Chlorotic Foliage</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Effective GSD</div>
              <div className="kpi-value purple">{droneData.gsd_cm_px} cm</div>
              <div className="kpi-sub">At 60m Altitude</div>
            </div>
          </div>
        </div>

        {/* Variable-Rate Spray Advisory Card */}
        <div className="card highlight-card">
          <div className="card-header">
            <div className="card-title text-emerald">
              <Sparkles size={18} color="#10b981" /> AI Variable-Rate Precision Spray Savings
            </div>
          </div>

          <p className="card-desc">
            Rather than spraying 100% of the field blindly, CropWatch Lite generates spot-application bounding coordinates for agricultural spray drones (e.g., DJI Agras T40).
          </p>

          <div className="savings-banner">
            <div className="savings-number">{droneData.precision_spray_advisory.chemical_and_cost_savings_pct}%</div>
            <div className="savings-text">
              <strong>Chemical &amp; Cost Reduction</strong>
              <span>Targeted fungicide spot application saves thousands in input costs and prevents chemical runoff.</span>
            </div>
          </div>

          <div className="spray-stats-list">
            <div className="spray-stat-item">
              <span>Conventional Blanket Spray Volume:</span>
              <strong>{droneData.precision_spray_advisory.conventional_spray_liters} Liters</strong>
            </div>
            <div className="spray-stat-item">
              <span>CropWatch AI Spot Spray Volume:</span>
              <strong className="text-emerald">{droneData.precision_spray_advisory.cropwatch_precision_spray_liters} Liters</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

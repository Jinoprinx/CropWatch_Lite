"use client";

import React, { useState, useEffect } from "react";
import { Sliders, Calculator, Wheat, PieChart } from "@/components/Icons";

interface YieldTabProps {
  initialDiseaseSeverity?: number;
  irrigationEfficiencyScore?: number;
  onAuditDataChange?: (data: {
    yieldResult: any;
    peakNdvi: number;
    gdd: number;
    rain: number;
    soc: number;
    diseasePct: number;
    anomalyPct: number;
  }) => void;
}

export const YieldTab: React.FC<YieldTabProps> = ({ initialDiseaseSeverity = 8.5, irrigationEfficiencyScore, onAuditDataChange }) => {
  const [loading, setLoading] = useState(false);
  const [crop, setCrop] = useState("corn");
  const [peakNdvi, setPeakNdvi] = useState(0.84);
  const [gdd, setGdd] = useState(1480);
  const [rain, setRain] = useState(465);
  const [vpd, setVpd] = useState(1.35);
  const [soc, setSoc] = useState(2.4);
  const [diseasePct, setDiseasePct] = useState(initialDiseaseSeverity);
  const [anomalyPct, setAnomalyPct] = useState(4.2);

  const [yieldResult, setYieldResult] = useState<any>({
    crop: "Corn",
    predicted_yield_tha: 11.4,
    predicted_yield_bu_ac: 181.6,
    regional_baseline_tha: 10.5,
    variance_vs_baseline_pct: 8.6,
    confidence_interval_90: { lower_bound_tha: 10.5, upper_bound_tha: 12.3 },
    yield_grade: "Optimal Yield (+8.6%)",
    impact_attribution: [
      {
        factor: "Vegetative Biomass (NDVI Peak)",
        impact_tha: 0.66,
        direction: "positive",
        notes: "Peak NDVI 0.84 indicates vigorous canopy light interception."
      },
      {
        factor: "Thermal Energy (GDD)",
        impact_tha: 0.25,
        direction: "positive",
        notes: "1480 GDD accumulated, meeting physiological maturity needs."
      },
      {
        factor: "Pathology & Stress Penalty",
        impact_tha: -0.84,
        direction: "negative",
        notes: "Disease severity (8.5%) & farm anomaly stress (4.2%)."
      }
    ]
  });

  useEffect(() => {
    runForecast();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runForecast = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/yield/forecast", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          crop,
          peak_ndvi: peakNdvi,
          ndvi_auc: peakNdvi * 88.0,
          peak_ndre: peakNdvi * 0.70,
          accumulated_gdd: gdd,
          total_precipitation_mm: rain,
          mean_vpd_kpa: vpd,
          soil_organic_carbon_pct: soc,
          available_water_capacity_mm: 165.0,
          detected_disease_severity_pct: diseasePct,
          farm_anomaly_area_pct: anomalyPct,
          ...(irrigationEfficiencyScore !== undefined && { irrigation_efficiency_score: irrigationEfficiencyScore }),
        })
      });
      const data = await res.json();
      setYieldResult(data);
      // Surface live farm data to audit modal
      onAuditDataChange?.({
        yieldResult: data,
        peakNdvi, gdd, rain, soc, diseasePct, anomalyPct,
      });
    } catch (err) {
      console.error("Yield forecast error:", err);
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
            <Sliders size={18} color="#10b981" /> Multimodal Yield Drivers &amp; Climate Inputs
          </div>
          <button className="btn btn-sm btn-primary" onClick={runForecast} disabled={loading}>
            <Calculator size={13} /> {loading ? "Forecasting..." : "Run Forecast Engine"}
          </button>
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label>Target Crop</label>
            <select className="form-select" value={crop} onChange={e => setCrop(e.target.value)}>
              <option value="corn">Corn (Maize)</option>
              <option value="soybean">Soybean</option>
              <option value="wheat">Wheat</option>
              <option value="tomato">Tomato</option>
              <option value="potato">Potato</option>
            </select>
          </div>

          <div className="form-group">
            <label>Peak NDVI (Canopy Biomass)</label>
            <input
              type="number"
              className="form-input"
              value={peakNdvi}
              step="0.01"
              min="0.3"
              max="0.98"
              onChange={e => setPeakNdvi(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Accumulated GDD (°C-Days)</label>
            <input
              type="number"
              className="form-input"
              value={gdd}
              step="10"
              onChange={e => setGdd(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Seasonal Precipitation (mm)</label>
            <input
              type="number"
              className="form-input"
              value={rain}
              step="5"
              onChange={e => setRain(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Mean Vapor Pressure Deficit (kPa)</label>
            <input
              type="number"
              className="form-input"
              value={vpd}
              step="0.05"
              onChange={e => setVpd(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Soil Organic Carbon (%)</label>
            <input
              type="number"
              className="form-input"
              value={soc}
              step="0.1"
              onChange={e => setSoc(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Detected Disease Severity (%)</label>
            <input
              type="number"
              className="form-input"
              value={diseasePct}
              step="0.5"
              onChange={e => setDiseasePct(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Spatial Farm Anomaly Area (%)</label>
            <input
              type="number"
              className="form-input"
              value={anomalyPct}
              step="0.1"
              onChange={e => setAnomalyPct(parseFloat(e.target.value))}
            />
          </div>
        </div>
      </div>

      {/* Right: Forecast Output & Impact Attribution */}
      <div className="card-column">
        {/* Main Forecast Hero */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Wheat size={18} color="#10b981" /> AI Harvest Projection (LightGBM Engine)
            </div>
            <span
              className={`badge ${
                yieldResult.variance_vs_baseline_pct >= 0 ? "badge-emerald" : "badge-amber"
              }`}
            >
              {yieldResult.yield_grade} ({yieldResult.variance_vs_baseline_pct > 0 ? "+" : ""}
              {yieldResult.variance_vs_baseline_pct}%)
            </span>
          </div>

          <div className="yield-hero">
            <div className="yield-primary">
              <span className="yield-huge">{yieldResult.predicted_yield_tha?.toFixed(1) || "11.4"}</span>
              <span className="yield-unit">Tonnes / Hectare</span>
            </div>
            <div className="yield-secondary">
              <span className="yield-bushels">{yieldResult.predicted_yield_bu_ac || "181.6"} bu/ac</span>
              <span className="yield-ci">
                90% CI: [{yieldResult.confidence_interval_90?.lower_bound_tha} -{" "}
                {yieldResult.confidence_interval_90?.upper_bound_tha} t/ha]
              </span>
            </div>
          </div>
        </div>

        {/* Feature Attribution List */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <PieChart size={18} /> Agronomic Attribution &amp; Limiting Factors
            </div>
          </div>

          <div className="impact-list">
            {yieldResult.impact_attribution?.map((attr: any, idx: number) => (
              <div key={idx} className="impact-item">
                <div>
                  <strong>{attr.factor}</strong>
                  <div style={{ fontSize: "11px", color: "var(--text-dim)" }}>{attr.notes}</div>
                </div>
                <span className={`impact-item-val ${attr.impact_tha >= 0 ? "pos" : "neg"}`}>
                  {attr.impact_tha > 0 ? "+" : ""}
                  {attr.impact_tha} t/ha
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

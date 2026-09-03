"use client";

import React, { useState, useEffect, useRef } from "react";
import { Camera, Dna, Leaf, FlaskConical, Tractor } from "@/components/Icons";

interface LeafDiseaseTabProps {
  onSeverityChange?: (severityPct: number) => void;
}

export const LeafDiseaseTab: React.FC<LeafDiseaseTabProps> = ({ onSeverityChange }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [samples, setSamples] = useState<any[]>([]);
  const [activeTreatmentTab, setActiveTreatmentTab] = useState<"organic" | "chemical" | "cultural">("organic");

  const [leafResult, setLeafResult] = useState<any>({
    disease_key: "tomato_early_blight",
    disease_name: "Early Blight of Tomato",
    crop: "Tomato",
    pathogen: "Alternaria solani (Fungus)",
    confidence: 0.948,
    severity_percentage: 16.8,
    severity_level: "moderate",
    severity_description: "Target-like brown lesions expanding with yellow halo. Moderate photosynthetic inhibition.",
    treatments: {
      organic: [
        "Bio-fungicide: Bacillus amyloliquefaciens foliar spray (Serenade ASO) at 4-8 L/ha.",
        "Liquid copper hydroxide (Kocide 3000) every 7-10 days."
      ],
      chemical: [
        "Chlorothalonil (Bravo Weather Stik) at 1.5-2.0 L/ha for protective coverage.",
        "Difenoconazole (Score 250 EC) at 0.5 L/ha for systemic translaminar eradication."
      ],
      cultural_practices: [
        "Stake and prune indeterminate vines to enhance airflow and suppress canopy humidity.",
        "Drip irrigation only; eliminate overhead sprinklers."
      ]
    },
    original_b64: "",
    annotated_image_base64: ""
  });

  useEffect(() => {
    async function fetchSamples() {
      try {
        const res = await fetch("http://localhost:8000/api/sample-assets");
        const data = await res.json();
        if (data.leaves && data.leaves.length > 0) {
          setSamples(data.leaves);
          analyzeLeaf(data.leaves[0].base64);
        }
      } catch (err) {
        console.error("Failed to load leaf samples:", err);
      }
    }
    fetchSamples();
  }, []);

  const analyzeLeaf = async (b64OrFile: string | File) => {
    setLoading(true);
    try {
      const form = new FormData();
      if (typeof b64OrFile === "string") {
        form.append("image_base64", b64OrFile);
      } else {
        form.append("file", b64OrFile);
      }

      const res = await fetch("http://localhost:8000/api/disease/analyze-leaf", {
        method: "POST",
        body: form
      });
      const data = await res.json();
      setLeafResult({
        ...data,
        original_b64: typeof b64OrFile === "string" ? b64OrFile : URL.createObjectURL(b64OrFile)
      });

      if (onSeverityChange) {
        onSeverityChange(data.severity_percentage);
      }
    } catch (e) {
      console.error("Leaf disease analysis failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      analyzeLeaf(e.target.files[0]);
    }
  };

  return (
    <div className="grid-layout-2col">
      {/* Left: Upload & Annotated Lesion Overlay */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Camera size={18} color="#a855f7" /> Close-Up Leaf Pathology Scanner
          </div>
          <span className="badge badge-purple">38+ Pathogen Taxonomy</span>
        </div>

        <div className="drone-upload-box" onClick={() => fileInputRef.current?.click()}>
          <Camera size={32} color="#a855f7" className="upload-icon" />
          <div className="upload-title">{loading ? "Diagnosing Pathology..." : "Drop Leaf Photo or Click to Upload"}</div>
          <div className="upload-sub">Instant edge computer vision lesion segmentation &amp; diagnostic profiling</div>
          <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileUpload} />
        </div>

        {samples.length > 0 && (
          <div className="sample-picker">
            <span>Or select field sample:</span>
            <div className="sample-buttons-wrap">
              {samples.map((s, idx) => (
                <button
                  key={s.filename}
                  className={`btn btn-xs ${idx === 0 ? "btn-success" : "btn-outline"}`}
                  onClick={() => analyzeLeaf(s.base64)}
                >
                  <Leaf size={11} color="#10b981" /> {s.name}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="leaf-analysis-view">
          <div className="image-box">
            <div className="image-tag">Original Leaf Input</div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={leafResult.original_b64 || "/placeholder.png"} alt="Original Leaf" />
          </div>
          <div className="image-box">
            <div className="image-tag">AI Necrotic Lesion Segmentation Overlay</div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={leafResult.annotated_image_base64 || "/placeholder.png"} alt="Lesion Overlay" />
          </div>
        </div>
      </div>

      {/* Right: Diagnosis & Prescription */}
      <div className="card-column">
        {/* Pathology Identification */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Dna size={18} color="#10b981" /> Pathology Classification &amp; Severity
            </div>
            <span
              className={`badge ${
                leafResult.severity_level === "severe"
                  ? "badge-red"
                  : leafResult.severity_level === "moderate"
                  ? "badge-amber"
                  : "badge-emerald"
              }`}
            >
              {leafResult.severity_level?.toUpperCase()} INFECTION
            </span>
          </div>

          <div className="disease-hero">
            <div className="disease-name">{leafResult.disease_name}</div>
            <div className="disease-meta">
              <span>Crop: <strong>{leafResult.crop}</strong></span> •{" "}
              <span>Pathogen: <em>{leafResult.pathogen}</em></span> •{" "}
              <span>Confidence: <strong className="text-emerald">{(leafResult.confidence * 100).toFixed(1)}%</strong></span>
            </div>
          </div>

          {/* Severity Gauge */}
          <div className="severity-section">
            <div className="severity-header">
              <span>Infected Leaf Area (% Severity):</span>
              <strong className="severity-pct-val">{leafResult.severity_percentage}%</strong>
            </div>
            <div className="severity-bar-bg">
              <div
                className="severity-bar-fill"
                style={{ width: `${Math.min(leafResult.severity_percentage * 3.5, 100)}%` }}
              />
            </div>
            <div className="severity-desc">{leafResult.severity_description}</div>
          </div>
        </div>

        {/* Treatment Prescription */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Agronomic Action &amp; Treatment Prescription</div>
          </div>

          <div className="treatment-tabs">
            <button
              className={`t-tab ${activeTreatmentTab === "organic" ? "active" : ""}`}
              onClick={() => setActiveTreatmentTab("organic")}
            >
              <Leaf size={13} color="#10b981" /> Organic / Bio-Controls
            </button>
            <button
              className={`t-tab ${activeTreatmentTab === "chemical" ? "active" : ""}`}
              onClick={() => setActiveTreatmentTab("chemical")}
            >
              <FlaskConical size={13} color="#06b6d4" /> Chemical Fungicides
            </button>
            <button
              className={`t-tab ${activeTreatmentTab === "cultural" ? "active" : ""}`}
              onClick={() => setActiveTreatmentTab("cultural")}
            >
              <Tractor size={13} color="#f59e0b" /> Cultural Practices
            </button>
          </div>

          <div className="treatment-body active">
            <ul className="treatment-list">
              {leafResult.treatments?.[
                activeTreatmentTab === "organic"
                  ? "organic"
                  : activeTreatmentTab === "chemical"
                  ? "chemical"
                  : "cultural_practices"
              ]?.map((item: string, idx: number) => (
                <li key={idx}>{item}</li>
              )) || <li>Standard monitoring recommended.</li>}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

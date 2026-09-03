"use client";

import React from "react";
import { FileContract, Printer, X } from "@/components/Icons";

interface AgronomyAuditModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AgronomyAuditModal: React.FC<AgronomyAuditModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <div className="modal-header">
          <div className="modal-title">
            <FileContract size={18} color="#10b981" /> Official Agronomy &amp; Harvest Audit Report
          </div>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div style={{ borderBottom: "1px solid var(--card-border)", paddingBottom: "14px", marginBottom: "16px" }}>
            <h2 style={{ color: "#fff", fontSize: "20px" }}>Precision Agronomy Diagnostic &amp; Harvest Audit</h2>
            <div style={{ color: "var(--emerald-primary)", fontSize: "13px" }}>
              CropWatch Lite Autonomous Intelligence System (Next.js Edition)
            </div>
            <div style={{ color: "var(--text-dim)", fontSize: "11px", marginTop: "4px" }}>
              Audit Generated: {new Date().toLocaleString()}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "20px" }}>
            <div style={{ background: "rgba(255,255,255,0.02)", padding: "14px", borderRadius: "8px" }}>
              <h4 style={{ color: "#fff", marginBottom: "6px" }}>1. Farm &amp; Spectral Health (Sentinel-2)</h4>
              <p>• Field: <strong>Oakridge Corn Sector Alpha</strong> (34.2 ha, CORN)</p>
              <p>• Mean NDVI: <strong>0.78</strong> (Vigorous Biomass)</p>
              <p>• Red-Edge NDRE: <strong>0.54</strong></p>
              <p>• Stress Hotspots: <strong>1 cluster</strong> (1.44 ha anomalous zone)</p>
            </div>

            <div style={{ background: "rgba(255,255,255,0.02)", padding: "14px", borderRadius: "8px" }}>
              <h4 style={{ color: "#fff", marginBottom: "6px" }}>2. UAV Photogrammetry &amp; Variable Spraying</h4>
              <p>• Ground Sampling Distance: <strong>2.5 cm/px</strong></p>
              <p>• Canopy Ground Cover: <strong>82.4%</strong></p>
              <p>
                • Chemical Reduction Savings:{" "}
                <strong style={{ color: "var(--emerald-primary)" }}>74.5% Reduction</strong>
              </p>
            </div>
          </div>

          <div style={{ background: "rgba(255,255,255,0.02)", padding: "14px", borderRadius: "8px", marginBottom: "20px" }}>
            <h4 style={{ color: "#fff", marginBottom: "6px" }}>3. AI Leaf Pathology Diagnosis &amp; Action Plan</h4>
            <p>
              • Pathogen Identification: <strong style={{ color: "#fff" }}>Northern Corn Leaf Blight</strong> (
              <em>Exserohilum turcicum</em>)
            </p>
            <p>• Severity Area: <strong>14.5%</strong> (MODERATE Level)</p>
            <p>• Primary Organic Action: <em>Bacillus subtilis bio-fungicide foliar misting.</em></p>
            <p>• Primary Chemical Prescription: <em>Azoxystrobin + Difenoconazole at 0.75 L/ha.</em></p>
          </div>

          <div
            style={{
              background: "linear-gradient(135deg, rgba(16,185,129,0.1), transparent)",
              border: "1px solid rgba(16,185,129,0.3)",
              padding: "16px",
              borderRadius: "8px"
            }}
          >
            <h4 style={{ color: "var(--emerald-primary)", marginBottom: "6px" }}>4. Final Harvest Forecast &amp; Confidence</h4>
            <div style={{ fontSize: "24px", fontWeight: 800, color: "#fff" }}>
              11.4 Tonnes / Hectare <span style={{ fontSize: "14px", color: "var(--text-muted)" }}>(181.6 bu/ac)</span>
            </div>
            <p style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
              Grade: Optimal Yield (+8.6%) • 90% Confidence Interval: [10.5 - 12.3 t/ha]
            </p>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={() => window.print()}>
            <Printer size={14} /> Print / Save as PDF
          </button>
          <button className="btn btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};

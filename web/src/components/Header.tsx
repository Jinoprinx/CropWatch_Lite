"use client";

import React from "react";
import { Sprout, Radio, Cpu, FileText } from "@/components/Icons";

interface HeaderProps {
  onOpenReport: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onOpenReport }) => {
  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-logo">
          <Sprout size={24} color="#ffffff" />
        </div>
        <div>
          <div className="brand-title">
            CropWatch <span className="brand-badge">NEXT.JS</span>
          </div>
          <div className="brand-subtitle">Autonomous Satellite &amp; Drone Crop Intelligence</div>
        </div>
      </div>

      <div className="header-stats">
        <div className="stat-pill">
          <span className="status-dot"></span>
          <span>Sentinel-2 BOA STAC: <strong>Connected</strong></span>
        </div>
        <div className="stat-pill">
          <Radio size={14} color="#06b6d4" />
          <span>RGB Photogrammetry: <strong>Ready</strong></span>
        </div>
        <div className="stat-pill">
          <Cpu size={14} color="#a855f7" />
          <span>Vision Diagnostics: <strong>Active</strong></span>
        </div>
      </div>

      <div className="header-actions">
        <button className="btn btn-primary" onClick={onOpenReport}>
          <FileText size={15} /> Export Agronomy Audit
        </button>
      </div>
    </header>
  );
};

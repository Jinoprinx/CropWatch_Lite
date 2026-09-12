"use client";

import React, { useState } from "react";
import { Header } from "@/components/Header";
import { SatelliteTab } from "@/components/SatelliteTab";
import { DroneTab } from "@/components/DroneTab";
import { LeafDiseaseTab } from "@/components/LeafDiseaseTab";
import { YieldTab } from "@/components/YieldTab";
import { FlightPlannerTab } from "@/components/FlightPlannerTab";
import { IrrigationTab } from "@/components/IrrigationTab";
import { AgronomyAuditModal } from "@/components/AgronomyAuditModal";
import { Satellite, Helicopter, Bug, TrendingUp, Compass, Droplets } from "@/components/Icons";

export default function Home() {
  const [activeTab, setActiveTab] = useState<"satellite" | "drone" | "disease" | "yield" | "planner" | "irrigation">("satellite");
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [leafDiseaseSeverity, setLeafDiseaseSeverity] = useState(14.5);
  const [irrigationEfficiencyScore, setIrrigationEfficiencyScore] = useState<number | null>(null);

  // Live farm data surfaced from YieldTab → passed to Audit Modal for recommendations
  const [farmAuditData, setFarmAuditData] = useState<{
    yieldResult?: any;
    peakNdvi?: number;
    gdd?: number;
    rain?: number;
    soc?: number;
    diseasePct?: number;
    anomalyPct?: number;
    irrigationEfficiencyScore?: number;
  }>({});

  return (
    <>
      <Header onOpenReport={() => setIsReportOpen(true)} />

      {/* Navigation Tabs */}
      <nav className="nav-tabs-container">
        <div className="nav-tabs">
          <button
            className={`nav-tab ${activeTab === "satellite" ? "active" : ""}`}
            onClick={() => setActiveTab("satellite")}
          >
            <Satellite size={15} /> 1. Macro Satellite (Sentinel-2)
          </button>
          <button
            className={`nav-tab ${activeTab === "drone" ? "active" : ""}`}
            onClick={() => setActiveTab("drone")}
          >
            <Helicopter size={15} /> 2. Meso Drone Photogrammetry
          </button>
          <button
            className={`nav-tab ${activeTab === "disease" ? "active" : ""}`}
            onClick={() => setActiveTab("disease")}
          >
            <Bug size={15} /> 3. Micro Leaf AI Diagnostics
          </button>
          <button
            className={`nav-tab ${activeTab === "yield" ? "active" : ""}`}
            onClick={() => setActiveTab("yield")}
          >
            <TrendingUp size={15} /> 4. Multimodal Yield Forecast
          </button>
          <button
            className={`nav-tab ${activeTab === "planner" ? "active" : ""}`}
            onClick={() => setActiveTab("planner")}
          >
            <Compass size={15} /> 5. Drone Mission &amp; Optics (ME)
          </button>
          <button
            className={`nav-tab ${activeTab === "irrigation" ? "active" : ""}`}
            onClick={() => setActiveTab("irrigation")}
            id="nav-tab-irrigation"
          >
            <Droplets size={15} /> 6. Smart Irrigation
          </button>
        </div>
      </nav>

      {/* Main Container */}
      <main className="main-container">
        {activeTab === "satellite" && (
          <div className="tab-content active">
            <SatelliteTab onSelectScoutHotspot={() => setActiveTab("drone")} />
          </div>
        )}

        {activeTab === "drone" && (
          <div className="tab-content active">
            <DroneTab />
          </div>
        )}

        {activeTab === "disease" && (
          <div className="tab-content active">
            <LeafDiseaseTab onSeverityChange={sev => setLeafDiseaseSeverity(sev)} />
          </div>
        )}

        {activeTab === "yield" && (
          <div className="tab-content active">
            <YieldTab
              initialDiseaseSeverity={leafDiseaseSeverity}
              irrigationEfficiencyScore={irrigationEfficiencyScore ?? undefined}
              onAuditDataChange={(data) => setFarmAuditData({ ...data, irrigationEfficiencyScore: irrigationEfficiencyScore ?? undefined })}
            />
          </div>
        )}

        {activeTab === "planner" && (
          <div className="tab-content active">
            <FlightPlannerTab />
          </div>
        )}

        {activeTab === "irrigation" && (
          <div className="tab-content active">
            <IrrigationTab onEfficiencyScoreChange={(score) => setIrrigationEfficiencyScore(score)} />
          </div>
        )}
      </main>

      {/* Report Modal */}
      <AgronomyAuditModal
        isOpen={isReportOpen}
        onClose={() => setIsReportOpen(false)}
        farmData={{
          ...farmAuditData,
          leafDiseaseSeverity,
          irrigationEfficiencyScore: irrigationEfficiencyScore ?? undefined,
        }}
      />
    </>
  );
}

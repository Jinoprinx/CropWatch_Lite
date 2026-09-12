"use client";
import React, { useState, useEffect, useCallback, useRef } from "react";
import { Droplets, Wifi, WifiOff, Gauge, Zap, Timer, Waves, RefreshCw, AlertTriangle, MapPin, Cpu } from "@/components/Icons";

interface SensorPacket {
  node_id: string; zone_id: string; vwc_pct: number;
  field_capacity_pct: number; permanent_wilting_point_pct: number;
  relative_saturation_pct: number; soil_temp_c: number;
  ec_ds_m: number; ec_status: string; battery_pct: number;
  battery_status: string; valve_open: boolean; status: string;
  location: { lat: number; lon: number }; soil_type: string;
  vwc_24h_trend?: number[];
}
interface ZoneDemand {
  zone_id: string; stress_label: string; stress_index: number;
  fused_demand_mm: number; mean_vwc_pct: number; min_vwc_pct: number;
  area_ha: number; iot_weight_escalated: boolean; w_satellite: number;
  w_iot: number; irrigate: boolean; mean_ndvi: number; mean_ndwi: number;
}
interface ValveCommand { zone_id: string; valve_open: boolean; duration_min: number; volume_litres: number; }
interface PumpStatus { running: boolean; speed_pct: number; flow_lpm: number; pressure_bar: number; power_kw: number; efficiency_pct: number; active_irrigation_zones: number; }
interface IrrigationResult {
  et0_mm_day: number; etc_mm_day: number; zone_demands: ZoneDemand[];
  valve_commands: ValveCommand[];
  pump_schedule: { total_irrigation_time_min: number; zone_sequence: any[] };
  irrigation_efficiency_score: number; water_savings_vs_uniform_pct: number;
  clog_alerts: any[]; seven_day_schedule: any[];
  satellite_layers?: { ndvi_heatmap?: string; ndwi_heatmap?: string }; mode: string;
}
interface IrrigationTabProps { onEfficiencyScoreChange?: (score: number) => void; }

const ZONE_LABELS: Record<string,string> = { zone_nw:"North-West", zone_ne:"North-East", zone_sw:"South-West", zone_se:"South-East" };
const API = "http://localhost:8000";

function getStressColor(label: string) {
  if (label === "critical") return { bg:"rgba(239,68,68,0.15)", border:"#ef4444", text:"#f87171" };
  if (label === "moderate") return { bg:"rgba(234,179,8,0.12)", border:"#ca8a04", text:"#facc15" };
  return { bg:"rgba(34,197,94,0.10)", border:"#16a34a", text:"#4ade80" };
}
function getVWCColor(vwc:number,fc:number,pwp:number){
  const p=((vwc-pwp)/Math.max(fc-pwp,1))*100;
  return p<25?"#ef4444":p<55?"#f59e0b":"#22c55e";
}

function BatteryIcon({pct}:{pct:number}){
  const c=pct>50?"#4ade80":pct>20?"#facc15":"#ef4444";
  return <span style={{fontSize:11,color:c,fontWeight:600}}>{pct>75?"▓▓▓▓":pct>50?"▓▓▓░":pct>25?"▓▓░░":"▓░░░"} {pct.toFixed(0)}%</span>;
}
function SectionHeader({icon,title,subtitle}:{icon:React.ReactNode;title:string;subtitle?:string}){
  return(
    <div className="irr-section-header">
      <div className="irr-section-icon">{icon}</div>
      <div><h3 className="irr-section-title">{title}</h3>{subtitle&&<p className="irr-section-subtitle">{subtitle}</p>}</div>
    </div>
  );
}
function MiniSparkline({data}:{data:number[]}){
  if(!data||data.length<2)return null;
  const h=28,w=80,min=Math.min(...data),max=Math.max(...data),range=Math.max(max-min,1);
  const pts=data.map((v,i)=>`${((i/(data.length-1))*w).toFixed(1)},${(h-((v-min)/range)*h).toFixed(1)}`).join(" ");
  return <svg width={w} height={h}><polyline points={pts} fill="none" stroke="#38bdf8" strokeWidth="1.5" strokeLinejoin="round"/></svg>;
}
function ZoneCard({zone,cmd}:{zone:ZoneDemand;cmd?:ValveCommand}){
  const c=getStressColor(zone.stress_label); const isActive=cmd?.valve_open;
  return(
    <div className={`irr-zone-card${isActive?" irr-zone-active":""}`} style={{background:c.bg,borderColor:c.border}}>
      {isActive&&<span className="irr-valve-pulse"/>}
      <div className="irr-zone-header">
        <span className="irr-zone-id">{ZONE_LABELS[zone.zone_id]||zone.zone_id}</span>
        <span className="irr-stress-badge" style={{background:c.border+"33",color:c.text}}>{zone.stress_label.toUpperCase()}</span>
      </div>
      <div className="irr-zone-metric">
        <span className="irr-zone-metric-val" style={{color:c.text}}>{zone.fused_demand_mm.toFixed(1)}<small> mm</small></span>
        <span className="irr-zone-metric-label">Water Demand</span>
      </div>
      <div className="irr-zone-stats">
        <div><span className="irr-stat-label">VWC</span><span className="irr-stat-val">{zone.mean_vwc_pct}%</span></div>
        <div><span className="irr-stat-label">NDVI</span><span className="irr-stat-val">{zone.mean_ndvi.toFixed(2)}</span></div>
        <div><span className="irr-stat-label">NDWI</span><span className="irr-stat-val">{zone.mean_ndwi.toFixed(2)}</span></div>
        <div><span className="irr-stat-label">Area</span><span className="irr-stat-val">{zone.area_ha} ha</span></div>
      </div>
      {zone.iot_weight_escalated&&<div className="irr-escalated-badge"><AlertTriangle size={11} color="#f59e0b"/> IoT weight escalated</div>}
      <div className="irr-weight-bars">
        <div className="irr-weight-row"><span>Sat</span><div className="irr-weight-track"><div className="irr-weight-fill irr-sat" style={{width:`${zone.w_satellite*100}%`}}/></div><span>{(zone.w_satellite*100).toFixed(0)}%</span></div>
        <div className="irr-weight-row"><span>IoT</span><div className="irr-weight-track"><div className="irr-weight-fill irr-iot" style={{width:`${zone.w_iot*100}%`}}/></div><span>{(zone.w_iot*100).toFixed(0)}%</span></div>
      </div>
      {cmd&&<div className="irr-valve-row"><span className={`irr-valve-led ${isActive?"open":"closed"}`}/><span>{isActive?`OPEN — ${cmd.duration_min.toFixed(0)} min`:"CLOSED"}</span></div>}
    </div>
  );
}
function SensorNodeCard({pkt}:{pkt:SensorPacket}){
  const vc=getVWCColor(pkt.vwc_pct,pkt.field_capacity_pct,pkt.permanent_wilting_point_pct);
  const fp=Math.max(0,Math.min(100,((pkt.vwc_pct-pkt.permanent_wilting_point_pct)/Math.max(pkt.field_capacity_pct-pkt.permanent_wilting_point_pct,1))*100));
  return(
    <div className="irr-sensor-card">
      <div className="irr-sensor-header">
        <span className="irr-sensor-zone">{pkt.zone_id.replace("zone_","").toUpperCase()}</span>
        <span className={`irr-valve-led ${pkt.valve_open?"open":"closed"}`} style={{width:10,height:10}}/>
        <span className="irr-sensor-id">{pkt.node_id.split("_").pop()}</span>
      </div>
      <div className="irr-vwc-container">
        <div className="irr-vwc-label"><span>Moisture</span><strong style={{color:vc}}>{pkt.vwc_pct.toFixed(1)}%</strong></div>
        <div className="irr-vwc-track"><div className="irr-vwc-fill" style={{width:`${fp}%`,background:vc}}/></div>
        <div className="irr-vwc-labels"><span style={{color:"#64748b"}}>{pkt.permanent_wilting_point_pct}% PWP</span><span style={{color:"#22d3ee"}}>{pkt.field_capacity_pct}% FC</span></div>
      </div>
      <div className="irr-sensor-stats">
        <div><span>Temp</span><span>{pkt.soil_temp_c.toFixed(1)}°C</span></div>
        <div><span>EC</span><span style={{color:pkt.ec_status==="critical"?"#ef4444":pkt.ec_status==="elevated"?"#f59e0b":"#4ade80"}}>{pkt.ec_ds_m.toFixed(2)} dS/m</span></div>
      </div>
      {pkt.vwc_24h_trend&&<MiniSparkline data={pkt.vwc_24h_trend}/>}
      <BatteryIcon pct={pkt.battery_pct}/>
      <div className="irr-sensor-status-badge" style={{color:pkt.status==="optimal"?"#4ade80":pkt.status.includes("critical")?"#ef4444":"#f59e0b"}}>{pkt.status.replace(/_/g," ")}</div>
    </div>
  );
}
function VFDGauge({pump}:{pump:PumpStatus}){
  const r=52,cx=64,cy=64,circ=2*Math.PI*r,arc=circ*0.75;
  const dash=arc-(pump.speed_pct/100)*arc;
  const pc=pump.pressure_bar>=3.0&&pump.pressure_bar<=4.0?"#4ade80":"#f59e0b";
  return(
    <div className="irr-pump-panel">
      <div className="irr-vfd-gauge">
        <svg width={128} height={128} viewBox="0 0 128 128">
          <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={10} strokeDasharray={`${arc} ${circ-arc}`} strokeDashoffset={circ*0.125} strokeLinecap="round" transform="rotate(135 64 64)"/>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={pump.running?"#38bdf8":"#334155"} strokeWidth={10} strokeDasharray={`${arc} ${circ}`} strokeDashoffset={dash+circ*0.125} strokeLinecap="round" transform="rotate(135 64 64)" style={{transition:"stroke-dashoffset 0.6s ease"}}/>
          <text x={cx} y={cy-6} textAnchor="middle" fill="#f1f5f9" fontSize={20} fontWeight="bold">{pump.speed_pct.toFixed(0)}%</text>
          <text x={cx} y={cy+12} textAnchor="middle" fill="#64748b" fontSize={9}>VFD SPEED</text>
        </svg>
      </div>
      <div className="irr-pump-stats">
        <div className="irr-pump-stat"><span className="irr-pump-label">Pressure</span><span className="irr-pump-val" style={{color:pc}}>{pump.pressure_bar.toFixed(2)} bar</span></div>
        <div className="irr-pump-stat"><span className="irr-pump-label">Flow</span><span className="irr-pump-val">{pump.flow_lpm.toFixed(0)} L/min</span></div>
        <div className="irr-pump-stat"><span className="irr-pump-label">Power</span><span className="irr-pump-val">{pump.power_kw.toFixed(1)} kW</span></div>
        <div className="irr-pump-stat"><span className="irr-pump-label">Efficiency</span><span className="irr-pump-val">{pump.efficiency_pct.toFixed(0)}%</span></div>
        <div className="irr-pump-stat"><span className="irr-pump-label">Active Zones</span><span className="irr-pump-val">{pump.active_irrigation_zones}</span></div>
      </div>
      <div className="irr-pump-status-badge" style={{background:pump.running?"rgba(56,189,248,0.15)":"rgba(71,85,105,0.3)",color:pump.running?"#38bdf8":"#64748b",borderColor:pump.running?"#38bdf8":"#475569"}}>
        <Zap size={12}/> {pump.running?"RUNNING":"STANDBY"}
      </div>
    </div>
  );
}
function EfficiencyGauge({score}:{score:number}){
  const pct=Math.round(score*100),c=pct>=80?"#4ade80":pct>=60?"#facc15":"#ef4444";
  const r=38,cx=48,cy=48,arc=2*Math.PI*r*0.75,fill=arc*(pct/100);
  return(
    <div className="irr-efficiency-gauge">
      <svg width={96} height={96} viewBox="0 0 96 96">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={8} strokeDasharray={`${arc} ${2*Math.PI*r-arc}`} strokeDashoffset={2*Math.PI*r*0.125} transform="rotate(135 48 48)"/>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={c} strokeWidth={8} strokeDasharray={`${fill} ${2*Math.PI*r}`} strokeDashoffset={(arc-fill)+2*Math.PI*r*0.125} strokeLinecap="round" transform="rotate(135 48 48)" style={{transition:"stroke-dashoffset 0.8s ease"}}/>
        <text x={cx} y={cy-4} textAnchor="middle" fill="#f1f5f9" fontSize={18} fontWeight="bold">{pct}%</text>
        <text x={cx} y={cy+10} textAnchor="middle" fill="#64748b" fontSize={7}>EFFICIENCY</text>
      </svg>
    </div>
  );
}

export function IrrigationTab({onEfficiencyScoreChange}:IrrigationTabProps){
  const [loading,setLoading]=useState(false);
  const [telLoading,setTelLoading]=useState(false);
  const [result,setResult]=useState<IrrigationResult|null>(null);
  const [telemetry,setTelemetry]=useState<SensorPacket[]>([]);
  const [pump,setPump]=useState<PumpStatus|null>(null);
  const [liveMode,setLiveMode]=useState(false);
  const [edgeFallback,setEdgeFallback]=useState(false);
  const [fallbackLog,setFallbackLog]=useState<any[]>([]);
  const [activeZoneCmd,setActiveZoneCmd]=useState<string|null>(null);
  const [schedDay,setSchedDay]=useState(0);
  const [crop,setCrop]=useState("corn");
  const [stage,setStage]=useState("peak_vegetative");
  const [fieldId,setFieldId]=useState("field_corn_01");
  const [tMax,setTMax]=useState("28.5");
  const [tMin,setTMin]=useState("14.2");
  const [rh,setRh]=useState("62.0");
  const [wind,setWind]=useState("2.1");
  const [solar,setSolar]=useState("18.5");
  const [rain,setRain]=useState("0.0");
  const liveRef=useRef<ReturnType<typeof setInterval>|null>(null);

  const fetchTelemetry=useCallback(async()=>{
    setTelLoading(true);
    try{const r=await fetch(`${API}/api/irrigation/telemetry/${fieldId}`);const d=await r.json();setTelemetry(d.telemetry||[]);}
    catch{}finally{setTelLoading(false);}
  },[fieldId]);
  const fetchPump=useCallback(async()=>{
    try{const r=await fetch(`${API}/api/irrigation/pump/status`);const d=await r.json();setPump(d);}catch{}
  },[]);
  useEffect(()=>{
    if(liveMode){fetchTelemetry();fetchPump();liveRef.current=setInterval(()=>{fetchTelemetry();fetchPump();},5000);}
    else{if(liveRef.current)clearInterval(liveRef.current);}
    return()=>{if(liveRef.current)clearInterval(liveRef.current);};
  },[liveMode,fetchTelemetry,fetchPump]);

  const runAnalysis=async()=>{
    setLoading(true);
    try{
      const body={field_id:fieldId,crop_type:crop,growth_stage:stage,t_max_c:parseFloat(tMax),t_min_c:parseFloat(tMin),rh_pct:parseFloat(rh),wind_speed_ms:parseFloat(wind),solar_rad_mj:parseFloat(solar),effective_rain_mm:parseFloat(rain)};
      const r=await fetch(`${API}/api/irrigation/analyze`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      const d=await r.json();setResult(d);
      if(d.irrigation_efficiency_score!==undefined)onEfficiencyScoreChange?.(d.irrigation_efficiency_score);
      await fetchTelemetry();await fetchPump();
    }catch{}finally{setLoading(false);}
  };
  const sendValveCmd=async(zoneId:string,cmd:"open"|"close")=>{
    setActiveZoneCmd(zoneId);
    try{await fetch(`${API}/api/irrigation/command/valve`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({zone_id:zoneId,command:cmd})});await fetchPump();}
    catch{}finally{setActiveZoneCmd(null);}
  };
  const toggleEdge=async()=>{
    if(!edgeFallback){
      try{const r=await fetch(`${API}/api/irrigation/edge-fallback/activate`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({field_id:fieldId,vwc_threshold_pct:28.0})});const d=await r.json();setFallbackLog(d.actions||[]);setEdgeFallback(true);}
      catch{setEdgeFallback(true);}
    }else{setEdgeFallback(false);setFallbackLog([]);}
  };

  const sched=result?.seven_day_schedule||[];
  const clogAlerts=result?.clog_alerts||[];
  const effScore=result?.irrigation_efficiency_score??null;

  return(
    <div className="irr-root">
      <div className="irr-hero">
        <div className="irr-hero-left">
          <div className="irr-hero-icon"><Droplets size={28} color="#38bdf8"/></div>
          <div>
            <h2 className="irr-hero-title">Smart Self-Healing Irrigation</h2>
            <p className="irr-hero-subtitle">Dual-stream NDVI + IoT fusion · FAO-56 ET₀ · VFD Pump Control · Edge Fallback</p>
          </div>
        </div>
        <div className="irr-hero-badges">
          <span className={`irr-conn-badge ${edgeFallback?"fallback":"connected"}`}>
            {edgeFallback?<WifiOff size={13}/>:<Wifi size={13}/>}
            {edgeFallback?"Edge Fallback Mode":"Cloud Connected"}
          </span>
          {effScore!==null&&<span className="irr-eff-badge">Efficiency {(effScore*100).toFixed(0)}%</span>}
        </div>
      </div>
      {clogAlerts.length>0&&<div className="irr-alert-banner"><AlertTriangle size={16} color="#f59e0b"/> {clogAlerts.length} drip clog alert(s): {clogAlerts[0]?.message}</div>}
      <div className="irr-controls-panel">
        <div className="irr-controls-grid">
          {[["Field",<select key="fi" className="irr-select" value={fieldId} onChange={e=>setFieldId(e.target.value)}><option value="field_corn_01">Oakridge Corn Sector Alpha</option><option value="field_soybean_02">Prairie View Soybean</option><option value="field_tomato_04">Valley Tomato</option></select>],
            ["Crop",<select key="cr" className="irr-select" value={crop} onChange={e=>setCrop(e.target.value)}>{["corn","wheat","soybean","tomato","potato","grape"].map(c=><option key={c} value={c}>{c.charAt(0).toUpperCase()+c.slice(1)}</option>)}</select>],
            ["Stage",<select key="st" className="irr-select" value={stage} onChange={e=>setStage(e.target.value)}><option value="early_emergence">Early Emergence</option><option value="peak_vegetative">Peak Vegetative</option><option value="senescence_harvest">Senescence</option></select>],
            ["T-Max (°C)",<input key="tm" className="irr-input" type="number" value={tMax} onChange={e=>setTMax(e.target.value)}/>],
            ["T-Min (°C)",<input key="tn" className="irr-input" type="number" value={tMin} onChange={e=>setTMin(e.target.value)}/>],
            ["RH (%)",<input key="rh" className="irr-input" type="number" value={rh} onChange={e=>setRh(e.target.value)}/>],
            ["Wind (m/s)",<input key="wi" className="irr-input" type="number" value={wind} onChange={e=>setWind(e.target.value)}/>],
            ["Solar (MJ)",<input key="so" className="irr-input" type="number" value={solar} onChange={e=>setSolar(e.target.value)}/>],
            ["Rain (mm)",<input key="ra" className="irr-input" type="number" value={rain} onChange={e=>setRain(e.target.value)}/>],
          ].map(([lbl,el],i)=>(
            <div key={i} className="irr-ctrl-group">
              <label className="irr-label">{lbl as string}</label>{el as React.ReactNode}
            </div>
          ))}
        </div>
        <div className="irr-btn-row">
          <button id="irr-analyze-btn" className="irr-btn-primary" onClick={runAnalysis} disabled={loading}>
            {loading?<RefreshCw size={14} className="spin"/>:<Waves size={14}/>} {loading?"Analyzing…":"Run Irrigation Cycle"}
          </button>
          <button id="irr-live-btn" className={`irr-btn-secondary${liveMode?" active":""}`} onClick={()=>setLiveMode(v=>!v)}>
            <Gauge size={14}/> {liveMode?"Live ON":"Live Mode"}
          </button>
          <button id="irr-fallback-btn" className={`irr-btn-danger${edgeFallback?" active":""}`} onClick={toggleEdge}>
            <WifiOff size={14}/> {edgeFallback?"Restore Cloud":"Edge Fallback"}
          </button>
        </div>
      </div>
      {result&&<>
        <div className="irr-et-summary">
          {[["ET₀ Reference",`${result.et0_mm_day} mm/day`],["Crop ETc",`${result.etc_mm_day} mm/day`],
            ["Water Savings",`${result.water_savings_vs_uniform_pct}% vs uniform`,"irr-savings"],
            ["Pump Time",`${result.pump_schedule?.total_irrigation_time_min?.toFixed(0)} min`],
            ["Zones Active",`${result.zone_demands?.filter(z=>z.irrigate).length} / ${result.zone_demands?.length}`]
          ].map(([lbl,val,cls],i)=>(
            <div key={i} className="irr-et-card">
              <span className="irr-et-label">{lbl}</span>
              <span className={`irr-et-val ${cls||""}`}>{val}</span>
            </div>
          ))}
        </div>
        <div className="irr-two-col">
          <div className="irr-section">
            <SectionHeader icon={<MapPin size={16} color="#38bdf8"/>} title="Field Irrigation Zones" subtitle="Satellite NDVI + IoT moisture fusion per zone"/>
            <div className="irr-zone-grid">
              {result.zone_demands.map(zone=>{
                const cmd=result.valve_commands.find(c=>c.zone_id===zone.zone_id);
                return <ZoneCard key={zone.zone_id} zone={zone} cmd={cmd}/>;
              })}
            </div>
            <div className="irr-valve-controls">
              {result.zone_demands.map(z=>(
                <div key={z.zone_id} className="irr-valve-ctrl-row">
                  <span>{ZONE_LABELS[z.zone_id]||z.zone_id}</span>
                  <button id={`valve-open-${z.zone_id}`} className="irr-valve-btn open" disabled={activeZoneCmd===z.zone_id} onClick={()=>sendValveCmd(z.zone_id,"open")}>Open</button>
                  <button id={`valve-close-${z.zone_id}`} className="irr-valve-btn close" disabled={activeZoneCmd===z.zone_id} onClick={()=>sendValveCmd(z.zone_id,"close")}>Close</button>
                </div>
              ))}
            </div>
          </div>
          <div className="irr-section">
            <SectionHeader icon={<Gauge size={16} color="#a78bfa"/>} title="VFD Pump Control" subtitle="Speed optimised per active zone (affinity laws)"/>
            {pump?<VFDGauge pump={pump}/>:<div className="irr-pump-placeholder"><Gauge size={40} color="#334155"/><p>Enable Live Mode or run analysis to view pump telemetry</p></div>}
            {result.pump_schedule?.zone_sequence?.length>0&&(
              <div className="irr-pump-schedule">
                <h4 className="irr-subsection-title">Zone Sequence</h4>
                {result.pump_schedule.zone_sequence.map((s:any,i:number)=>(
                  <div key={i} className="irr-schedule-row">
                    <span className="irr-sched-zone">{ZONE_LABELS[s.zone_id]||s.zone_id}</span>
                    <span className="irr-sched-time">+{s.start_offset_min?.toFixed(0)} min</span>
                    <span className="irr-sched-duration">{s.duration_min?.toFixed(0)} min</span>
                    <span className="irr-sched-speed" style={{color:"#38bdf8"}}>{s.pump_speed_pct}% VFD</span>
                  </div>
                ))}
              </div>
            )}
            <div className="irr-efficiency-panel">
              <SectionHeader icon={<Zap size={15} color="#facc15"/>} title="Irrigation Efficiency" subtitle="Tightens yield CI from ±7.5% to ±5.0%"/>
              <div className="irr-efficiency-body">
                <EfficiencyGauge score={effScore??0}/>
                <div className="irr-efficiency-stats">
                  <p>Score: <strong style={{color:"#4ade80"}}>{((effScore??0)*100).toFixed(1)}%</strong></p>
                  <p>Without irrigation: <strong>±7.5% CI</strong></p>
                  <p>With this score: <strong style={{color:"#4ade80"}}>±5.0% CI</strong></p>
                  <p style={{fontSize:11,color:"#64748b",marginTop:4}}>Auto-applied when navigating to Yield tab.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
        {sched.length>0&&(
          <div className="irr-section">
            <SectionHeader icon={<Timer size={16} color="#34d399"/>} title="7-Day Irrigation Schedule" subtitle="ET₀ persistence · Off-peak window planning"/>
            <div className="irr-sched-tabs">
              {sched.map((day:any,i:number)=>(
                <button key={i} className={`irr-sched-tab${schedDay===i?" active":""}${day.skip_irrigation?" skip":""}`} onClick={()=>setSchedDay(i)}>
                  <span className="irr-sched-tab-day">{day.date?.slice(5)}</span>
                  <span className="irr-sched-tab-mm">{day.skip_irrigation?"Skip":`${day.net_irrigation_mm} mm`}</span>
                </button>
              ))}
            </div>
            {sched[schedDay]&&(
              <div className="irr-sched-detail">
                <div className="irr-sched-detail-header">
                  {[["ET₀",sched[schedDay].et0_mm,"mm"],["ETc",sched[schedDay].etc_mm,"mm"],["Rain",sched[schedDay].rain_forecast_mm,"mm"],["Net",sched[schedDay].net_irrigation_mm,"mm"],["Vol",(sched[schedDay].total_volume_litres/1000).toFixed(1),"m³"]].map(([l,v,u],i)=>(
                    <div key={i}><span className="irr-sched-detail-label">{l}</span><span>{v}</span><small>{u}</small></div>
                  ))}
                </div>
                <div className="irr-sched-zones">
                  {(sched[schedDay].zones||[]).map((z:any)=>(
                    <div key={z.zone_id} className={`irr-sched-zone-row${z.skip?" skip":""}`}>
                      <span>{ZONE_LABELS[z.zone_id]||z.zone_id}</span>
                      {z.skip?<span style={{color:"#475569"}}>Skip</span>:<>
                        <span style={{color:"#38bdf8"}}>{z.demand_mm} mm</span>
                        <span>{z.duration_min?.toFixed(0)} min</span>
                        <span style={{color:"#64748b",fontSize:11}}>{z.scheduled_open?.slice(11,16)}</span>
                      </>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </>}
      <div className="irr-section">
        <div className="irr-section-title-row">
          <SectionHeader icon={<Cpu size={16} color="#fb923c"/>} title="IoT Sensor Network — 8 ESP32 Nodes" subtitle="Capacitive VWC · Soil Temp · EC · Relay · 24h Trend"/>
          <button id="irr-refresh-telemetry-btn" className="irr-btn-secondary small" onClick={fetchTelemetry} disabled={telLoading}>
            <RefreshCw size={12} className={telLoading?"spin":""}/> Refresh
          </button>
        </div>
        {telemetry.length===0?
          <div className="irr-sensor-empty"><Cpu size={36} color="#334155"/><p>Run an analysis or enable Live Mode to stream sensor telemetry.</p></div>:
          <div className="irr-sensor-grid">{telemetry.map(pkt=><SensorNodeCard key={pkt.node_id} pkt={pkt}/>)}</div>
        }
      </div>
      {edgeFallback&&(
        <div className="irr-section irr-fallback-section">
          <SectionHeader icon={<WifiOff size={16} color="#f87171"/>} title="Edge Fallback Active" subtitle="Cloud-offline mode — autonomous threshold-based decisions"/>
          <div className="irr-fallback-log">
            {fallbackLog.length===0?<p style={{color:"#64748b",fontSize:13}}>No fallback decisions yet.</p>:
              fallbackLog.map((e,i)=>(
                <div key={i} className="irr-fallback-entry">
                  <span className="irr-fallback-time">{e.timestamp_utc?.slice(11,19)}</span>
                  <span className="irr-fallback-zone">{ZONE_LABELS[e.zone_id]||e.zone_id}</span>
                  <span>VWC {e.min_vwc_pct}%</span>
                  <span className={`irr-fallback-action ${e.action?.includes("open")?"irrigate":"skip"}`}>{e.action?.replace(/_/g," ")}</span>
                </div>
              ))
            }
          </div>
        </div>
      )}
    </div>
  );
}

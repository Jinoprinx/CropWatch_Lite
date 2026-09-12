"""
CropWatch Lite - Smart Irrigation: Dual-Stream Fusion Engine
AWS Lambda-equivalent Python fusion engine that combines:
  1. Low-frequency macro Sentinel-2 NDVI/NDWI satellite zone maps
  2. High-frequency micro IoT capacitive sensor telemetry
to compute precise zone-level water demand, valve scheduling, VFD pump speed,
a 7-day irrigation calendar, and an irrigation efficiency score fed back into
the YieldPredictor to tighten confidence intervals.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

import numpy as np


# -----------------------------------------------------------------
# Crop Coefficients (Kc) — FAO-56 Table 12 (simplified)
# -----------------------------------------------------------------
CROP_KC: Dict[str, Dict[str, float]] = {
    "corn":    {"early_emergence": 0.30, "peak_vegetative": 1.20, "senescence_harvest": 0.60},
    "maize":   {"early_emergence": 0.30, "peak_vegetative": 1.20, "senescence_harvest": 0.60},
    "wheat":   {"early_emergence": 0.30, "peak_vegetative": 1.15, "senescence_harvest": 0.25},
    "soybean": {"early_emergence": 0.40, "peak_vegetative": 1.15, "senescence_harvest": 0.50},
    "tomato":  {"early_emergence": 0.60, "peak_vegetative": 1.15, "senescence_harvest": 0.80},
    "potato":  {"early_emergence": 0.50, "peak_vegetative": 1.15, "senescence_harvest": 0.75},
    "grape":   {"early_emergence": 0.30, "peak_vegetative": 0.85, "senescence_harvest": 0.45},
}

# VWC thresholds that trigger IoT weight escalation
IOT_CRITICAL_VWC = 28.0   # % below which sensor data takes priority
IOT_WEIGHT_NORMAL = 0.45
IOT_WEIGHT_CRITICAL = 0.80
SAT_WEIGHT_NORMAL = 0.55
SAT_WEIGHT_CRITICAL = 0.20

EMITTER_FLOW_LPH = 8.0          # litres per hour per drip emitter
EMITTERS_PER_HA = 1250           # typical drip layout
TARGET_PRESSURE_BAR = 3.5


# -----------------------------------------------------------------
# Data Classes (plain dicts for JSON-serialisability)
# -----------------------------------------------------------------

def _make_zone(zone_id: str, row: int, col: int, mean_ndvi: float,
               mean_ndwi: float, anomaly_flag: bool, area_ha: float) -> Dict[str, Any]:
    """Construct an IrrigationZone dict."""
    # NDWI < 0.1 indicates moisture stress; NDVI < 0.45 indicates poor canopy
    ndwi_stress = max(0.0, (0.25 - mean_ndwi) / 0.35)
    ndvi_stress = max(0.0, (0.70 - mean_ndvi) / 0.50)
    stress_index = round(min(1.0, 0.6 * ndwi_stress + 0.4 * ndvi_stress + (0.15 if anomaly_flag else 0.0)), 3)
    return {
        "zone_id": zone_id,
        "row": row, "col": col,
        "area_ha": round(area_ha, 2),
        "mean_ndvi": round(float(mean_ndvi), 3),
        "mean_ndwi": round(float(mean_ndwi), 3),
        "anomaly_flagged": anomaly_flag,
        "stress_index": stress_index,
        "stress_label": ("critical" if stress_index > 0.60 else
                         "moderate" if stress_index > 0.30 else "optimal"),
    }


# -----------------------------------------------------------------
# Main Engine
# -----------------------------------------------------------------

class IrrigationFusionEngine:
    """
    Dual-stream precision irrigation fusion engine.
    Combines Sentinel-2 satellite NDVI/NDWI zone maps with IoT sensor
    telemetry to compute zone water demand, issue hardware commands,
    and generate a 7-day irrigation schedule.
    """

    def __init__(self):
        pass

    # ================================================================
    # A.  NDVI → Zone Stress Mapping
    # ================================================================

    def map_ndvi_to_zones(
        self,
        satellite_scene: Dict[str, Any],
        num_zones: int = 4,
        total_field_ha: float = 34.2,
        anomaly_hotspots: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Divide NDVI/NDWI rasters into N grid zones and compute per-zone
        stress index by fusing spectral deficit signals.
        """
        indices = satellite_scene.get("indices", {})
        ndvi_raster = np.asarray(indices.get("ndvi", [[]]), dtype=np.float32)
        ndwi_raster = np.asarray(indices.get("ndwi", [[]]), dtype=np.float32)

        h, w = ndvi_raster.shape
        cols = rows = int(math.sqrt(num_zones))
        if rows * cols < num_zones:
            cols += 1

        zone_ha = total_field_ha / num_zones
        zone_labels = ["NW", "NE", "SW", "SE", "NC", "SC", "WC", "EC"]
        anomaly_zone_ids: set = set()

        # Map hotspot GPS to approximate zone (by fraction of grid)
        if anomaly_hotspots:
            for hs in anomaly_hotspots:
                # Simple heuristic: use lat/lon offsets to estimate quadrant
                anomaly_zone_ids.add(zone_labels[0])  # mark NW as placeholder

        zones = []
        z_idx = 0
        for r in range(rows):
            for c in range(cols):
                if z_idx >= num_zones:
                    break
                r_start = int(r * h / rows)
                r_end   = int((r + 1) * h / rows)
                c_start = int(c * w / cols)
                c_end   = int((c + 1) * w / cols)

                ndvi_patch = ndvi_raster[r_start:r_end, c_start:c_end]
                ndwi_patch = ndwi_raster[r_start:r_end, c_start:c_end]

                label = zone_labels[z_idx] if z_idx < len(zone_labels) else f"Z{z_idx+1}"
                has_anomaly = label in anomaly_zone_ids

                zone = _make_zone(
                    zone_id=label,
                    row=r, col=c,
                    mean_ndvi=float(np.mean(ndvi_patch)) if ndvi_patch.size else 0.5,
                    mean_ndwi=float(np.mean(ndwi_patch)) if ndwi_patch.size else 0.1,
                    anomaly_flag=has_anomaly,
                    area_ha=zone_ha,
                )
                zones.append(zone)
                z_idx += 1

        return zones

    # ================================================================
    # B.  FAO-56 Penman-Monteith ET₀
    # ================================================================

    def calculate_et0_penman_monteith(
        self,
        t_max_c: float,
        t_min_c: float,
        rh_pct: float,
        wind_speed_ms: float,
        solar_rad_mj: float,
        altitude_m: float = 0.0,
        day_of_year: int = 180,
    ) -> float:
        """
        FAO-56 Penman-Monteith Reference Evapotranspiration (mm/day).
        Allen et al. (1998) — FAO Irrigation and Drainage Paper 56.
        """
        t_mean = (t_max_c + t_min_c) / 2.0

        # Atmospheric pressure (kPa) at altitude
        P = 101.3 * ((293.0 - 0.0065 * altitude_m) / 293.0) ** 5.26

        # Psychrometric constant
        gamma = 0.000665 * P

        # Saturation vapour pressure (kPa)
        def svp(t: float) -> float:
            return 0.6108 * math.exp(17.27 * t / (t + 237.3))

        e_s = (svp(t_max_c) + svp(t_min_c)) / 2.0
        e_a = svp(t_mean) * (rh_pct / 100.0)
        vpd = max(0.0, e_s - e_a)

        # Slope of saturation vapour pressure curve
        delta = 4098.0 * svp(t_mean) / ((t_mean + 237.3) ** 2)

        # Net radiation (MJ m⁻² day⁻¹) — approximate from incoming solar
        Rns = (1.0 - 0.23) * solar_rad_mj  # Net short-wave (albedo 0.23)
        sigma = 4.903e-9  # MJ m⁻² day⁻¹ K⁻⁴
        T_max_k = t_max_c + 273.16
        T_min_k = t_min_c + 273.16
        ea_kPa  = max(e_a, 0.01)
        Rnl = (sigma * (T_max_k ** 4 + T_min_k ** 4) / 2.0
               * (0.34 - 0.14 * math.sqrt(ea_kPa))
               * (1.35 * (solar_rad_mj / max(solar_rad_mj * 1.1, 0.01)) - 0.35))
        Rn = Rns - Rnl

        # Soil heat flux (G) ≈ 0 for daily calculations
        G = 0.0

        # Wind speed at 2m height (measured at 2m assumed)
        u2 = wind_speed_ms

        # FAO-56 PM equation
        numerator = (0.408 * delta * (Rn - G)
                     + gamma * (900.0 / (t_mean + 273.0)) * u2 * vpd)
        denominator = delta + gamma * (1.0 + 0.34 * u2)
        et0 = max(0.0, numerator / max(denominator, 1e-6))
        return round(et0, 2)

    def calculate_crop_etc(self, et0: float, crop: str, growth_stage: str) -> float:
        """ETc = ET₀ × Kc  (crop evapotranspiration, mm/day)."""
        crop_kc = CROP_KC.get(crop.lower(), CROP_KC["corn"])
        kc = crop_kc.get(growth_stage, crop_kc["peak_vegetative"])
        return round(et0 * kc, 2)

    # ================================================================
    # C.  Dual-Stream Fusion → Zone Demand
    # ================================================================

    def fuse_satellite_iot(
        self,
        zones: List[Dict[str, Any]],
        telemetry_packets: List[Dict[str, Any]],
        etc_mm_day: float,
        effective_rain_mm: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Fuse satellite stress zones with IoT ground-truth telemetry.
        Applies dynamic weight escalation when VWC is critically low.
        Returns per-zone water demand (mm) and valve command parameters.
        """
        # Build zone → node telemetry mapping
        zone_telemetry: Dict[str, List[Dict[str, Any]]] = {}
        for pkt in telemetry_packets:
            zone_telemetry.setdefault(pkt["zone_id"], []).append(pkt)

        zone_demands = []
        for zone in zones:
            zone_id = zone["zone_id"]
            stress_index = zone["stress_index"]

            # Satellite-derived demand component
            sat_demand_mm = etc_mm_day * (1.0 + stress_index * 0.4) - effective_rain_mm
            sat_demand_mm = max(0.0, sat_demand_mm)

            # IoT ground-truth component
            pkts = zone_telemetry.get(zone_id, [])
            if pkts:
                vwc_vals = [p["vwc_pct"] for p in pkts]
                mean_vwc = sum(vwc_vals) / len(vwc_vals)
                min_vwc  = min(vwc_vals)
                fc_pct   = pkts[0].get("field_capacity_pct", 38.0)
                pwp_pct  = pkts[0].get("permanent_wilting_point_pct", 18.0)
                # Deficit from field capacity (mm per 100mm root depth)
                deficit_mm = max(0.0, (fc_pct - mean_vwc) / 100.0 * 300.0)  # 300mm root depth
            else:
                min_vwc = 35.0
                mean_vwc = 35.0
                deficit_mm = etc_mm_day * (1.0 + stress_index * 0.3)

            # Dynamic weight escalation
            if min_vwc < IOT_CRITICAL_VWC:
                w_iot = IOT_WEIGHT_CRITICAL
                w_sat = SAT_WEIGHT_CRITICAL
                escalated = True
            else:
                w_iot = IOT_WEIGHT_NORMAL
                w_sat = SAT_WEIGHT_NORMAL
                escalated = False

            # Fused demand
            fused_mm = (sat_demand_mm * w_sat) + (deficit_mm * w_iot)
            # Quantize to nearest 0.5mm for valve timing precision
            fused_mm = round(math.ceil(fused_mm * 2.0) / 2.0, 1)
            fused_mm = max(0.0, min(fused_mm, 30.0))  # Cap at 30mm/cycle

            zone_demands.append({
                "zone_id": zone_id,
                "stress_index": stress_index,
                "stress_label": zone["stress_label"],
                "mean_ndvi": zone["mean_ndvi"],
                "mean_ndwi": zone["mean_ndwi"],
                "area_ha": zone["area_ha"],
                "satellite_demand_mm": round(sat_demand_mm, 2),
                "iot_deficit_mm": round(deficit_mm, 2),
                "w_satellite": w_sat,
                "w_iot": w_iot,
                "iot_weight_escalated": escalated,
                "fused_demand_mm": fused_mm,
                "mean_vwc_pct": round(mean_vwc, 1),
                "min_vwc_pct": round(min_vwc, 1),
                "irrigate": fused_mm > 0.5,
                "anomaly_flagged": zone.get("anomaly_flagged", False),
            })

        return sorted(zone_demands, key=lambda x: x["fused_demand_mm"], reverse=True)

    # ================================================================
    # D.  Valve & VFD Pump Command Generator
    # ================================================================

    def generate_valve_commands(
        self,
        zone_demands: List[Dict[str, Any]],
        emitter_flow_lph: float = EMITTER_FLOW_LPH,
        emitters_per_ha: int = EMITTERS_PER_HA,
    ) -> List[Dict[str, Any]]:
        """Convert zone water demand (mm) → valve open duration (min) + MQTT payload."""
        commands = []
        for zd in zone_demands:
            area_ha = zd["area_ha"]
            demand_mm = zd["fused_demand_mm"]
            # Volume (L) = demand_mm × area_m² × 1L/m²/mm
            volume_litres = demand_mm * area_ha * 10000.0
            total_flow_lph = emitter_flow_lph * emitters_per_ha * area_ha
            duration_hours = volume_litres / max(total_flow_lph, 1.0)
            duration_min = round(duration_hours * 60.0, 1)

            commands.append({
                "zone_id": zd["zone_id"],
                "valve_open": zd["irrigate"] and demand_mm > 0.0,
                "duration_min": duration_min if zd["irrigate"] else 0.0,
                "fused_demand_mm": demand_mm,
                "volume_litres": round(volume_litres, 0),
                "mqtt_topic": f"cropwatch/commands/{zd['zone_id']}",
                "payload": {
                    "action": "irrigate" if zd["irrigate"] else "skip",
                    "duration_min": duration_min,
                    "demand_mm": demand_mm,
                    "priority": "high" if zd["stress_label"] == "critical" else "normal",
                },
            })
        return commands

    def calculate_pump_schedule(
        self,
        valve_commands: List[Dict[str, Any]],
        target_pressure_bar: float = TARGET_PRESSURE_BAR,
        emitter_flow_lph: float = EMITTER_FLOW_LPH,
        emitters_per_zone: int = 120,
    ) -> Dict[str, Any]:
        """
        Sequential pump schedule: one zone at a time to maintain target pressure.
        Computes VFD speed (%) using affinity laws for each active zone.
        """
        NOMINAL_PRESSURE = 4.5
        NOMINAL_FLOW_LPM = 420.0

        schedule = []
        elapsed_min = 0.0

        for cmd in valve_commands:
            if not cmd["valve_open"]:
                continue
            duration = cmd["duration_min"]
            flow_lpm = (emitter_flow_lph * emitters_per_zone) / 60.0
            speed_ratio = math.sqrt(target_pressure_bar / NOMINAL_PRESSURE)
            flow_ratio  = flow_lpm / NOMINAL_FLOW_LPM
            speed_pct   = max(speed_ratio, flow_ratio) * 100.0
            speed_pct   = round(min(speed_pct, 100.0), 1)

            schedule.append({
                "zone_id": cmd["zone_id"],
                "start_offset_min": round(elapsed_min, 1),
                "duration_min": duration,
                "end_offset_min": round(elapsed_min + duration, 1),
                "pump_speed_pct": speed_pct,
                "estimated_pressure_bar": round(NOMINAL_PRESSURE * (speed_pct / 100.0) ** 2, 2),
                "flow_lpm": round(flow_lpm, 1),
            })
            elapsed_min += duration + 2.0  # 2-min transition buffer between zones

        return {
            "total_irrigation_time_min": round(elapsed_min, 1),
            "total_zones_active": len(schedule),
            "target_pressure_bar": target_pressure_bar,
            "zone_sequence": schedule,
        }

    # ================================================================
    # E.  7-Day Irrigation Schedule Lookahead
    # ================================================================

    def build_7day_schedule(
        self,
        crop: str,
        growth_stage: str,
        et0_today: float,
        zone_demands_today: List[Dict[str, Any]],
        effective_rain_forecast_mm: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Project a 7-day irrigation schedule using a simple ET₀ persistence model.
        Each day gets a recommended start time and per-zone volume.
        """
        kc = CROP_KC.get(crop.lower(), CROP_KC["corn"]).get(growth_stage, 1.0)
        rain_forecast = effective_rain_forecast_mm or [0.0] * 7
        schedule = []

        base_date = datetime.now(timezone.utc).replace(hour=5, minute=0, second=0, microsecond=0)

        for day in range(7):
            # ET₀ drifts slightly each day (persistence with 5% random variation)
            et0_day = round(et0_today * (1.0 + (day * 0.01) * (-1 if day % 2 else 1)), 2)
            etc_day = round(et0_day * kc, 2)
            rain_day = rain_forecast[day] if day < len(rain_forecast) else 0.0
            net_req   = max(0.0, etc_day - rain_day)
            skip_day  = net_req < 1.0 or (rain_day > 5.0)

            zone_windows = []
            start_dt = base_date + timedelta(days=day)
            offset_min = 0.0
            for zd in zone_demands_today:
                daily_mm = round(zd["fused_demand_mm"] * (net_req / max(etc_day, 0.01)), 1)
                daily_mm = max(0.0, daily_mm) if not skip_day else 0.0
                area_ha   = zd["area_ha"]
                vol_litres = daily_mm * area_ha * 10000.0
                flow_lph  = EMITTER_FLOW_LPH * EMITTERS_PER_HA * area_ha
                dur_min   = round((vol_litres / max(flow_lph, 1.0)) * 60.0, 1)

                open_time = (start_dt + timedelta(minutes=offset_min)).isoformat()
                zone_windows.append({
                    "zone_id": zd["zone_id"],
                    "scheduled_open": open_time,
                    "duration_min": dur_min,
                    "demand_mm": daily_mm,
                    "volume_litres": round(vol_litres, 0),
                    "skip": skip_day or daily_mm < 0.5,
                })
                offset_min += dur_min + 2.0

            total_vol = sum(zw["volume_litres"] for zw in zone_windows if not zw["skip"])
            schedule.append({
                "day": day + 1,
                "date": (base_date + timedelta(days=day)).strftime("%Y-%m-%d"),
                "et0_mm": et0_day,
                "etc_mm": etc_day,
                "rain_forecast_mm": rain_day,
                "net_irrigation_mm": round(net_req, 2),
                "skip_irrigation": skip_day,
                "total_volume_litres": round(total_vol, 0),
                "zones": zone_windows,
            })

        return schedule

    # ================================================================
    # F.  Irrigation Efficiency Score
    # ================================================================

    def compute_irrigation_efficiency(
        self,
        zone_demands: List[Dict[str, Any]],
        telemetry_packets: List[Dict[str, Any]],
    ) -> float:
        """
        Score 0.0–1.0 reflecting how precisely water was delivered.
        Penalises over-watering (VWC > field capacity) and under-watering (VWC < PWP + 5%).
        """
        if not zone_demands or not telemetry_packets:
            return 0.75  # Default neutral score

        zone_tel: Dict[str, List[Dict]] = {}
        for pkt in telemetry_packets:
            zone_tel.setdefault(pkt["zone_id"], []).append(pkt)

        scores = []
        for zd in zone_demands:
            zone_id = zd["zone_id"]
            pkts = zone_tel.get(zone_id, [])
            if not pkts:
                scores.append(0.70)
                continue
            vwc_vals = [p["vwc_pct"] for p in pkts]
            fc_vals  = [p.get("field_capacity_pct", 38.0) for p in pkts]
            pwp_vals = [p.get("permanent_wilting_point_pct", 18.0) for p in pkts]
            mean_vwc = sum(vwc_vals) / len(vwc_vals)
            mean_fc  = sum(fc_vals)  / len(fc_vals)
            mean_pwp = sum(pwp_vals) / len(pwp_vals)
            # Optimal range: 65–90% of field capacity
            optimal_lo = mean_pwp + 0.65 * (mean_fc - mean_pwp)
            optimal_hi = mean_pwp + 0.90 * (mean_fc - mean_pwp)

            if optimal_lo <= mean_vwc <= optimal_hi:
                zone_score = 1.0
            elif mean_vwc < optimal_lo:
                deficit_frac = (optimal_lo - mean_vwc) / max(optimal_lo - mean_pwp, 1.0)
                zone_score = max(0.0, 1.0 - deficit_frac * 1.2)
            else:
                excess_frac = (mean_vwc - optimal_hi) / max(mean_fc - optimal_hi, 1.0)
                zone_score = max(0.0, 1.0 - excess_frac * 0.8)
            scores.append(zone_score)

        return round(sum(scores) / len(scores), 3)

    # ================================================================
    # G.  Full Cycle Orchestrator
    # ================================================================

    def run_full_cycle(
        self,
        field_id: str,
        crop: str,
        growth_stage: str,
        satellite_scene: Dict[str, Any],
        telemetry_packets: List[Dict[str, Any]],
        t_max_c: float = 28.5,
        t_min_c: float = 14.2,
        rh_pct: float = 62.0,
        wind_speed_ms: float = 2.1,
        solar_rad_mj: float = 18.5,
        altitude_m: float = 310.0,
        effective_rain_mm: float = 0.0,
        num_zones: int = 4,
        total_field_ha: float = 34.2,
        anomaly_hotspots: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrates the full dual-stream irrigation decision cycle.
        Returns zone demands, valve commands, pump schedule, 7-day lookahead,
        and the irrigation efficiency score ready for YieldPredictor.
        """
        # Step 1: ET₀ and ETc
        et0 = self.calculate_et0_penman_monteith(
            t_max_c, t_min_c, rh_pct, wind_speed_ms, solar_rad_mj, altitude_m
        )
        etc = self.calculate_crop_etc(et0, crop, growth_stage)

        # Step 2: NDVI zone mapping
        zones = self.map_ndvi_to_zones(
            satellite_scene, num_zones=num_zones,
            total_field_ha=total_field_ha,
            anomaly_hotspots=anomaly_hotspots or [],
        )

        # Step 3: Dual-stream fusion
        zone_demands = self.fuse_satellite_iot(zones, telemetry_packets, etc, effective_rain_mm)

        # Step 4: Valve commands
        valve_commands = self.generate_valve_commands(zone_demands)

        # Step 5: Pump schedule
        pump_schedule = self.calculate_pump_schedule(valve_commands)

        # Step 6: 7-day schedule
        seven_day = self.build_7day_schedule(crop, growth_stage, et0, zone_demands)

        # Step 7: Efficiency score
        efficiency_score = self.compute_irrigation_efficiency(zone_demands, telemetry_packets)

        # Water savings estimate vs. uniform blanket irrigation
        uniform_demand_mm = etc * total_field_ha * 10000.0 / 1000.0  # m³
        precision_demand_m3 = sum(vc["volume_litres"] for vc in valve_commands) / 1000.0
        water_savings_pct = round(max(0.0, (1.0 - precision_demand_m3 / max(uniform_demand_mm, 1.0))) * 100.0, 1)

        return {
            "field_id": field_id,
            "cycle_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "crop": crop,
            "growth_stage": growth_stage,
            "weather_inputs": {
                "t_max_c": t_max_c, "t_min_c": t_min_c, "rh_pct": rh_pct,
                "wind_speed_ms": wind_speed_ms, "solar_rad_mj": solar_rad_mj,
            },
            "et0_mm_day": et0,
            "etc_mm_day": etc,
            "effective_rain_mm": effective_rain_mm,
            "zone_map": zones,
            "zone_demands": zone_demands,
            "valve_commands": valve_commands,
            "pump_schedule": pump_schedule,
            "seven_day_schedule": seven_day,
            "irrigation_efficiency_score": efficiency_score,
            "water_savings_vs_uniform_pct": water_savings_pct,
            "total_zones": num_zones,
            "zones_requiring_irrigation": sum(1 for z in zone_demands if z["irrigate"]),
            "total_water_volume_litres": sum(vc["volume_litres"] for vc in valve_commands),
            "mode": "cloud_fusion",
        }

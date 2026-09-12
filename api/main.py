"""
CropWatch Lite - FastAPI Backend Server
Unified precision agriculture REST API for Satellite Ingest, Drone Photogrammetry,
AI Multi-Scale Disease Detection, Yield Forecasting, and Flight Mission Planning.
"""

import os
import json
import base64
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core.indices import SpectralIndices
from core.satellite_pipeline import SatellitePipeline
from core.drone_pipeline import DronePipeline
from core.disease_detector import DiseaseDetector
from core.anomaly_detector import AnomalyDetector
from core.weather_soil import WeatherSoilEngine
from core.yield_predictor import YieldPredictor
from core.flight_planner import DroneFlightPlanner
from core.irrigation_telemetry import IrrigationTelemetry
from core.irrigation_engine import IrrigationFusionEngine

app = FastAPI(
    title="CropWatch Lite API",
    description="Low-Cost High-Efficiency Precision Agriculture Platform (Health + Disease Detection + Yield Forecasting)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Core Engines
satellite_engine = SatellitePipeline()
drone_engine = DronePipeline()
disease_engine = DiseaseDetector()
anomaly_engine = AnomalyDetector()
yield_engine = YieldPredictor()
irrigation_telemetry = IrrigationTelemetry()
irrigation_engine = IrrigationFusionEngine()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


# ------------------- Request Models ------------------- #
class SatelliteAnalysisRequest(BaseModel):
    bbox: Optional[List[float]] = [-93.650, 42.018, -93.642, 42.025]
    crop_type: Optional[str] = "corn"
    growth_stage: Optional[str] = "peak_vegetative"
    origin_lat: Optional[float] = 42.0215
    origin_lon: Optional[float] = -93.6460


class LeafAnalysisBase64Request(BaseModel):
    image_base64: str


class YieldForecastRequest(BaseModel):
    crop: str = "corn"
    peak_ndvi: float = 0.84
    ndvi_auc: float = 74.0
    peak_ndre: float = 0.58
    accumulated_gdd: float = 1480.0
    total_precipitation_mm: float = 465.0
    mean_vpd_kpa: float = 1.35
    soil_organic_carbon_pct: float = 2.4
    available_water_capacity_mm: float = 165.0
    detected_disease_severity_pct: float = 0.0
    farm_anomaly_area_pct: float = 0.0
    irrigation_efficiency_score: Optional[float] = None


class IrrigationAnalysisRequest(BaseModel):
    field_id: str = "field_corn_01"
    crop_type: str = "corn"
    growth_stage: str = "peak_vegetative"
    bbox: Optional[List[float]] = [-93.650, 42.018, -93.642, 42.025]
    origin_lat: Optional[float] = 42.021
    origin_lon: Optional[float] = -93.646
    num_zones: int = 4
    total_field_ha: float = 34.2
    t_max_c: float = 28.5
    t_min_c: float = 14.2
    rh_pct: float = 62.0
    wind_speed_ms: float = 2.1
    solar_rad_mj: float = 18.5
    altitude_m: float = 310.0
    effective_rain_mm: float = 0.0


class ValveCommandRequest(BaseModel):
    zone_id: str
    command: str = "open"
    duration_min: Optional[float] = None


class EdgeFallbackRequest(BaseModel):
    field_id: str = "field_corn_01"
    vwc_threshold_pct: float = 28.0


class FlightPlanRequest(BaseModel):
    field_area_ha: float = 25.0
    camera_type: str = "dji_mavic_3e"
    flight_altitude_m: float = 60.0
    forward_overlap_pct: float = 75.0
    side_overlap_pct: float = 70.0
    flight_speed_m_s: float = 7.5
    battery_flight_time_min: float = 24.0


# ------------------- API Endpoints ------------------- #
@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "system": "CropWatch Lite Precision Agriculture Suite",
        "version": "1.1.0",
        "modules": {
            "indices_engine": "active",
            "sentinel_satellite_ingest": "active",
            "drone_photogrammetry": "active",
            "leaf_disease_diagnostics": "active",
            "spatial_anomaly_detector": "active",
            "multimodal_yield_predictor": "active",
            "hardware_flight_planner": "active",
            "smart_irrigation_system": "active",
        }
    }


@app.get("/api/fields")
def get_sample_fields():
    fields_file = os.path.join(DATA_DIR, "sample_fields", "fields.geojson")
    if os.path.exists(fields_file):
        with open(fields_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"type": "FeatureCollection", "features": []}


@app.get("/api/sample-assets")
def get_sample_assets():
    """Returns list of preloaded sample leaf and drone images with base64 previews."""
    leaf_dir = os.path.join(DATA_DIR, "sample_leaves")
    drone_dir = os.path.join(DATA_DIR, "sample_drone")

    leaves = []
    if os.path.exists(leaf_dir):
        for fname in os.listdir(leaf_dir):
            if fname.endswith((".jpg", ".png", ".jpeg")):
                fpath = os.path.join(leaf_dir, fname)
                with open(fpath, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                leaves.append({
                    "filename": fname,
                    "name": fname.replace(".jpg", "").replace("_", " ").title(),
                    "base64": f"data:image/jpeg;base64,{b64}"
                })

    drone_tiles = []
    if os.path.exists(drone_dir):
        for fname in os.listdir(drone_dir):
            if fname.endswith((".jpg", ".png", ".jpeg")):
                fpath = os.path.join(drone_dir, fname)
                with open(fpath, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                drone_tiles.append({
                    "filename": fname,
                    "name": fname.replace(".jpg", "").replace("_", " ").title(),
                    "base64": f"data:image/jpeg;base64,{b64}"
                })

    return {"leaves": leaves, "drone_tiles": drone_tiles}


@app.post("/api/satellite/analyze")
def analyze_satellite_field(req: SatelliteAnalysisRequest):
    """
    Simulates / Ingests Sentinel-2 L2A BOA imagery for the field boundary,
    calculates NDVI/NDRE/EVI/NDWI rasters, and runs spatial anomaly clustering.
    """
    scene = satellite_engine.generate_synthetic_sentinel_scene(
        bbox=req.bbox,
        crop_type=req.crop_type,
        growth_stage=req.growth_stage
    )

    # Detect farm anomalies & stress clusters
    anomaly_res = anomaly_engine.detect_field_anomalies(
        primary_index=scene["indices"]["ndvi"],
        red_edge_index=scene["indices"]["ndre"],
        water_index=scene["indices"]["ndwi"],
        pixel_size_meters=scene["spatial_resolution_m"],
        origin_lat=req.origin_lat,
        origin_lon=req.origin_lon
    )

    return {
        "crop_type": req.crop_type,
        "growth_stage": req.growth_stage,
        "satellite": "Sentinel-2 L2A (10m Multi-Spectral)",
        "summary_indices": scene["summary_stats"],
        "anomaly_analysis": anomaly_res,
        "layers": {
            "true_color": scene["true_color_b64"],
            "ndvi_heatmap": scene["ndvi_heatmap_b64"],
            "ndre_heatmap": scene["ndre_heatmap_b64"],
            "ndwi_heatmap": scene["ndwi_heatmap_b64"]
        }
    }


@app.post("/api/drone/analyze")
async def analyze_drone_image(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
    gsd_cm: float = Form(2.5),
    altitude_m: float = Form(60.0)
):
    """
    Processes drone RGB aerial image: calculates visible-band indices (VARI, GLI, ExG),
    canopy coverage %, stressed foliage %, and variable-rate precision spraying savings.
    """
    img_bytes = None
    if file:
        img_bytes = await file.read()
    elif image_base64:
        img_bytes = image_base64
    else:
        # Fallback to default sample drone tile
        sample_path = os.path.join(DATA_DIR, "sample_drone", "drone_crop_canopy_ortho.jpg")
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                img_bytes = f.read()
        else:
            raise HTTPException(status_code=400, detail="No image provided")

    result = drone_engine.process_orthomosaic_tile(
        image_input=img_bytes,
        gsd_cm_per_pixel=gsd_cm,
        altitude_m=altitude_m
    )
    return result


@app.post("/api/disease/analyze-leaf")
async def analyze_leaf_image(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None)
):
    """
    Classifies leaf pathology, computes lesion infection severity area %,
    and prescribes organic/chemical/cultural treatments.
    """
    img_data = None
    if file:
        img_data = await file.read()
    elif image_base64:
        img_data = image_base64
    else:
        sample_path = os.path.join(DATA_DIR, "sample_leaves", "tomato_early_blight.jpg")
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                img_data = f.read()
        else:
            raise HTTPException(status_code=400, detail="No image provided")

    result = disease_engine.analyze_image(img_data)
    return result


@app.post("/api/yield/forecast")
def forecast_yield(req: YieldForecastRequest):
    """
    Fuses vegetative phenology, climate (GDD, rain, VPD), soil attributes,
    and disease stress penalties to forecast yield with 90% CI and explainability.
    Optionally accepts an irrigation_efficiency_score from the Smart Irrigation module
    to tighten confidence intervals and apply a precision water correction.
    """
    result = yield_engine.predict_yield(
        crop=req.crop,
        peak_ndvi=req.peak_ndvi,
        ndvi_auc=req.ndvi_auc,
        peak_ndre=req.peak_ndre,
        accumulated_gdd=req.accumulated_gdd,
        total_precipitation_mm=req.total_precipitation_mm,
        mean_vpd_kpa=req.mean_vpd_kpa,
        soil_organic_carbon_pct=req.soil_organic_carbon_pct,
        available_water_capacity_mm=req.available_water_capacity_mm,
        detected_disease_severity_pct=req.detected_disease_severity_pct,
        farm_anomaly_area_pct=req.farm_anomaly_area_pct,
        irrigation_efficiency_score=req.irrigation_efficiency_score,
    )
    return result


@app.post("/api/drone/flight-plan")
def calculate_flight_plan(req: FlightPlanRequest):
    """
    Calculates drone photogrammetry GSD, flight lines, mission time, and battery logistics.
    """
    return DroneFlightPlanner.calculate_photogrammetry_mission(
        field_area_ha=req.field_area_ha,
        camera_type=req.camera_type,
        flight_altitude_m=req.flight_altitude_m,
        forward_overlap_pct=req.forward_overlap_pct,
        side_overlap_pct=req.side_overlap_pct,
        flight_speed_m_s=req.flight_speed_m_s,
        battery_flight_time_min=req.battery_flight_time_min
    )


# ------------------- Smart Irrigation Endpoints ------------------- #

@app.post("/api/irrigation/analyze")
def analyze_irrigation(req: IrrigationAnalysisRequest):
    """
    Full dual-stream irrigation decision cycle:
    Sentinel-2 NDVI zone mapping + IoT sensor fusion → zone water demands,
    valve commands, VFD pump schedule, 7-day irrigation lookahead,
    and an irrigation efficiency score ready for the Yield Predictor.
    """
    # 1. Ensure sensor network is initialised for this field
    registry = irrigation_telemetry.generate_field_sensor_network(
        field_id=req.field_id,
    )

    # 2. Fetch synthetic Sentinel-2 scene (reuses existing satellite pipeline)
    satellite_scene = satellite_engine.generate_synthetic_sentinel_scene(
        bbox=req.bbox,
        crop_type=req.crop_type,
        growth_stage=req.growth_stage,
    )

    # 3. Detect anomalies for zone flagging
    anomaly_res = anomaly_engine.detect_field_anomalies(
        primary_index=satellite_scene["indices"]["ndvi"],
        red_edge_index=satellite_scene["indices"]["ndre"],
        water_index=satellite_scene["indices"]["ndwi"],
        pixel_size_meters=satellite_scene["spatial_resolution_m"],
        origin_lat=req.origin_lat,
        origin_lon=req.origin_lon,
    )

    # 4. Get current IoT telemetry
    telemetry = irrigation_telemetry.get_current_telemetry()

    # 5. Run full fusion cycle
    result = irrigation_engine.run_full_cycle(
        field_id=req.field_id,
        crop=req.crop_type,
        growth_stage=req.growth_stage,
        satellite_scene=satellite_scene,
        telemetry_packets=telemetry,
        t_max_c=req.t_max_c,
        t_min_c=req.t_min_c,
        rh_pct=req.rh_pct,
        wind_speed_ms=req.wind_speed_ms,
        solar_rad_mj=req.solar_rad_mj,
        altitude_m=req.altitude_m,
        effective_rain_mm=req.effective_rain_mm,
        num_zones=req.num_zones,
        total_field_ha=req.total_field_ha,
        anomaly_hotspots=anomaly_res.get("hotspots", []),
    )

    # 6. Check for drip clog alerts
    clog_alerts = irrigation_telemetry.detect_drip_clog()

    result["sensor_registry"] = registry
    result["anomaly_analysis"] = anomaly_res
    result["clog_alerts"] = clog_alerts
    result["satellite_layers"] = {
        "ndvi_heatmap": satellite_scene["ndvi_heatmap_b64"],
        "ndwi_heatmap": satellite_scene["ndwi_heatmap_b64"],
    }
    return result


@app.get("/api/irrigation/telemetry/{field_id}")
def get_irrigation_telemetry(field_id: str):
    """
    Returns live telemetry from all 8 IoT sensor nodes in the field.
    Advances sensor state by one 5-minute tick to simulate real-time streaming.
    """
    # Init network if not yet done for this field
    if not irrigation_telemetry._nodes:
        irrigation_telemetry.generate_field_sensor_network(field_id=field_id)

    packets = irrigation_telemetry.stream_all_telemetry(advance_minutes=5.0)
    zone_summary = irrigation_telemetry.get_zone_summary()
    clog_alerts = irrigation_telemetry.detect_drip_clog()

    return {
        "field_id": field_id,
        "node_count": len(packets),
        "cloud_connected": irrigation_telemetry.is_cloud_connected,
        "edge_fallback_active": irrigation_telemetry.is_edge_fallback_active,
        "telemetry": packets,
        "zone_summary": zone_summary,
        "clog_alerts": clog_alerts,
    }


@app.post("/api/irrigation/command/valve")
def send_valve_command(req: ValveCommandRequest):
    """
    Send an open or close command to a specific irrigation zone valve.
    Simulates MQTT publish to the ESP32 relay controller.
    """
    open_valve = req.command.lower() == "open"
    ack = irrigation_telemetry.simulate_relay_command(req.zone_id, open_valve=open_valve)
    pump_status = irrigation_telemetry.get_pump_status()
    return {
        "command_ack": ack,
        "pump_status": pump_status,
    }


@app.get("/api/irrigation/pump/status")
def get_pump_status():
    """Returns current VFD pump telemetry: speed %, pressure, flow rate, power."""
    if not irrigation_telemetry._nodes:
        irrigation_telemetry.generate_field_sensor_network(field_id="field_corn_01")
    return irrigation_telemetry.get_pump_status()


@app.post("/api/irrigation/edge-fallback/activate")
def activate_edge_fallback(req: EdgeFallbackRequest):
    """
    Activates local edge fallback mode — all irrigation decisions switch to
    simple VWC threshold rules without requiring cloud connectivity.
    Simulates the ESP32 local autonomous controller.
    """
    if not irrigation_telemetry._nodes:
        irrigation_telemetry.generate_field_sensor_network(field_id=req.field_id)
    return irrigation_telemetry.activate_edge_fallback(vwc_threshold_pct=req.vwc_threshold_pct)


@app.get("/api/irrigation/schedule/{field_id}")
def get_irrigation_schedule(field_id: str, crop: str = "corn", growth_stage: str = "peak_vegetative"):
    """
    Returns a 7-day optimised irrigation schedule with per-zone daily windows,
    ET₀ projections, and estimated water volumes.
    """
    if not irrigation_telemetry._nodes:
        irrigation_telemetry.generate_field_sensor_network(field_id=field_id)

    # Use default weather for schedule projection
    et0 = irrigation_engine.calculate_et0_penman_monteith(
        t_max_c=28.5, t_min_c=14.2, rh_pct=62.0,
        wind_speed_ms=2.1, solar_rad_mj=18.5, altitude_m=310.0
    )
    etc = irrigation_engine.calculate_crop_etc(et0, crop, growth_stage)

    # Build minimal zone demand list for schedule
    zone_summary = irrigation_telemetry.get_zone_summary()
    minimal_demands = []
    for zone_id, summary in zone_summary.items():
        fc = 38.0
        deficit_mm = max(0.0, (fc - summary["mean_vwc_pct"]) / 100.0 * 300.0)
        minimal_demands.append({
            "zone_id": zone_id,
            "fused_demand_mm": round(min(deficit_mm, 15.0), 1),
            "area_ha": 8.55,  # Default quarter-field
            "irrigate": deficit_mm > 1.0,
        })

    seven_day = irrigation_engine.build_7day_schedule(crop, growth_stage, et0, minimal_demands)

    return {
        "field_id": field_id,
        "crop": crop,
        "growth_stage": growth_stage,
        "et0_reference_mm_day": et0,
        "etc_mm_day": etc,
        "seven_day_schedule": seven_day,
    }


# ------------------- Frontend Static Files ------------------- #
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "CropWatch Lite backend is running. Frontend index.html not yet built."}

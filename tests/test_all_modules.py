"""
CropWatch Lite - Comprehensive Test Suite
Validates mathematical integrity of spectral indices, drone photogrammetry,
leaf pathology classification, spatial anomaly clustering, and yield forecasting.
"""

import os
import pytest
import numpy as np
from PIL import Image

from core.indices import SpectralIndices
from core.satellite_pipeline import SatellitePipeline
from core.drone_pipeline import DronePipeline
from core.disease_detector import DiseaseDetector
from core.anomaly_detector import AnomalyDetector
from core.weather_soil import WeatherSoilEngine
from core.yield_predictor import YieldPredictor
from core.flight_planner import DroneFlightPlanner


def test_spectral_indices():
    nir = np.array([0.5, 0.6, 0.4])
    red = np.array([0.1, 0.2, 0.05])
    ndvi = SpectralIndices.ndvi(nir, red)
    assert np.all(ndvi >= -1.0) and np.all(ndvi <= 1.0)
    assert ndvi[0] == pytest.approx((0.5 - 0.1) / (0.5 + 0.1), abs=1e-3)

    # Test VARI
    green = np.array([0.4, 0.5])
    blue = np.array([0.1, 0.1])
    vari = SpectralIndices.vari(green, red[:2], blue)
    assert np.all(vari >= -1.0) and np.all(vari <= 1.0)


def test_satellite_pipeline_synthetic_scene():
    pipeline = SatellitePipeline()
    res = pipeline.generate_synthetic_sentinel_scene(
        bbox=[-93.65, 42.018, -93.64, 42.025],
        crop_type="corn",
        growth_stage="peak_vegetative",
        grid_dim=(50, 50)
    )
    assert "indices" in res
    assert "ndvi" in res["indices"]
    assert res["summary_stats"]["mean_ndvi"] > 0.4
    assert res["ndvi_heatmap_b64"].startswith("data:image/png;base64,")


def test_spatial_anomaly_detector():
    detector = AnomalyDetector(z_thresh=-1.5, min_cluster_pixels=3)
    ndvi_grid = np.ones((50, 50), dtype=np.float32) * 0.8
    # Inject a low NDVI stress zone
    ndvi_grid[20:30, 20:30] = 0.25

    res = detector.detect_field_anomalies(
        primary_index=ndvi_grid,
        origin_lat=42.0,
        origin_lon=-93.6
    )
    assert res["status"] == "success"
    assert res["anomaly_count"] >= 1
    assert res["anomalous_area_pct"] > 0.0
    assert len(res["hotspots"]) >= 1
    assert "latitude" in res["hotspots"][0]


def test_drone_pipeline():
    drone = DronePipeline()
    # Create test RGB image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :, 1] = 180 # lush green
    img[:, :, 0] = 40
    img[:, :, 2] = 30

    res = drone.process_orthomosaic_tile(img, gsd_cm_per_pixel=2.0, altitude_m=50.0)
    assert res["canopy_coverage_percentage"] > 80.0
    assert res["healthy_canopy_pct"] > 70.0
    assert "precision_spray_advisory" in res
    assert res["heatmap_base64"].startswith("data:image/jpeg;base64,")


def test_disease_detector():
    detector = DiseaseDetector()
    # Create test synthetic image with dark spots
    img = Image.new("RGB", (200, 200), (45, 140, 45))
    res = detector.analyze_image(img)
    assert "disease_key" in res
    assert "confidence" in res
    assert "severity_percentage" in res
    assert "treatments" in res
    assert "organic" in res["treatments"]
    assert "chemical" in res["treatments"]
    assert res["annotated_image_base64"].startswith("data:image/jpeg;base64,")


def test_weather_soil_and_gdd():
    t_max = np.array([28.0, 30.0, 32.0, 29.0])
    t_min = np.array([16.0, 18.0, 19.0, 17.0])
    gdd_res = WeatherSoilEngine.calculate_gdd(t_max, t_min, crop="corn")
    assert gdd_res["total_accumulated_gdd"] > 0
    assert len(gdd_res["daily_gdd"]) == 4

    weather_profile = WeatherSoilEngine.generate_season_weather_profile("corn", 60)
    assert "climate_summary" in weather_profile
    assert weather_profile["climate_summary"]["total_gdd"] > 500.0


def test_yield_predictor():
    predictor = YieldPredictor()
    pred_healthy = predictor.predict_yield(
        crop="corn",
        peak_ndvi=0.86,
        accumulated_gdd=1550.0,
        detected_disease_severity_pct=0.0,
        farm_anomaly_area_pct=0.0
    )
    assert pred_healthy["predicted_yield_tha"] > 9.0
    assert "confidence_interval_90" in pred_healthy

    # Stress case with high disease
    pred_diseased = predictor.predict_yield(
        crop="corn",
        peak_ndvi=0.68,
        accumulated_gdd=1550.0,
        detected_disease_severity_pct=28.0,
        farm_anomaly_area_pct=15.0
    )
    assert pred_diseased["predicted_yield_tha"] < pred_healthy["predicted_yield_tha"]


def test_flight_planner():
    plan = DroneFlightPlanner.calculate_photogrammetry_mission(
        field_area_ha=30.0,
        camera_type="dji_mavic_3e",
        flight_altitude_m=70.0
    )
    assert plan["gsd_cm_per_pixel"] > 0
    assert plan["flight_lines_count"] > 0
    assert plan["estimated_flight_time_minutes"] > 0
    assert plan["batteries_needed"] >= 1

    spray_plan = DroneFlightPlanner.calculate_spray_drone_logistics(
        target_spray_area_ha=10.0,
        target_rate_liters_per_ha=20.0
    )
    assert spray_plan["total_fungicide_mix_liters"] == 200.0
    assert spray_plan["required_tank_payload_refills"] >= 10

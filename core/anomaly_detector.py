"""
CropWatch Lite - Farm & Canopy Anomaly Detector
Spatial statistical anomaly engine for detecting early pre-symptomatic infection clusters,
Red-Edge chlorophyll collapse, and moisture deficit zones across agricultural fields.
"""

from typing import Dict, Any, List, Tuple
import numpy as np
from scipy import ndimage


class AnomalyDetector:
    """
    Detects localized agronomic anomalies and infection hotspots in 2D vegetation index grids.
    Combines spatial z-scoring, morphological cluster analysis, and Red-Edge deficit detection.
    """

    def __init__(self, z_thresh: float = -1.75, min_cluster_pixels: int = 5):
        self.z_thresh = z_thresh
        self.min_cluster_pixels = min_cluster_pixels

    def detect_field_anomalies(
        self,
        primary_index: np.ndarray,
        red_edge_index: np.ndarray = None,
        water_index: np.ndarray = None,
        valid_mask: np.ndarray = None,
        pixel_size_meters: float = 10.0,
        origin_lat: float = 40.7128,
        origin_lon: float = -74.0060,
    ) -> Dict[str, Any]:
        """
        Scans a 2D raster grid of a field (NDVI/VARI), finds statistical outlier zones,
        checks Red-Edge disparity (pre-visual pathogen alert), and extracts GPS anomaly polygons.
        """
        arr = np.asarray(primary_index, dtype=np.float32)
        if valid_mask is None:
            # Mask out non-crop or invalid zero/NaN values
            valid_mask = ~np.isnan(arr) & (arr > 0.05)

        if np.sum(valid_mask) < 20:
            return {
                "status": "insufficient_data",
                "anomaly_count": 0,
                "anomalous_area_ha": 0.0,
                "anomalous_area_pct": 0.0,
                "hotspots": [],
                "anomaly_heatmap": None
            }

        valid_vals = arr[valid_mask]
        mean_val = float(np.mean(valid_vals))
        std_val = float(np.std(valid_vals)) + 1e-6

        # 1. Compute Spatial Z-Score
        z_score_grid = np.zeros_like(arr)
        z_score_grid[valid_mask] = (arr[valid_mask] - mean_val) / std_val

        # 2. Thresholding for stress/disease zones (values significantly lower than field average)
        stress_binary = (z_score_grid < self.z_thresh) & valid_mask

        # 3. If Red-Edge index is provided, detect early pre-symptomatic stress (NDRE drops faster than NDVI)
        early_red_edge_stress = np.zeros_like(arr, dtype=bool)
        if red_edge_index is not None:
            re_arr = np.asarray(red_edge_index, dtype=np.float32)
            re_valid = re_arr[valid_mask]
            re_mean = float(np.mean(re_valid))
            re_std = float(np.std(re_valid)) + 1e-6
            re_z = np.zeros_like(re_arr)
            re_z[valid_mask] = (re_arr[valid_mask] - re_mean) / re_std
            # Red-edge deficit: RE drops more than 1.5 sigma below normal
            early_red_edge_stress = (re_z < -1.5) & valid_mask
            stress_binary = stress_binary | early_red_edge_stress

        # 4. Connected Component Morphological Clustering
        labeled_array, num_features = ndimage.label(stress_binary)
        
        hotspots = []
        total_anomaly_pixels = 0
        height, width = arr.shape

        # Approximate lat/lon scaling
        meters_per_deg_lat = 111320.0
        meters_per_deg_lon = 111320.0 * np.cos(np.radians(origin_lat))

        for feat_id in range(1, num_features + 1):
            feat_mask = labeled_array == feat_id
            feat_pixels = int(np.sum(feat_mask))
            if feat_pixels < self.min_cluster_pixels:
                continue

            total_anomaly_pixels += feat_pixels
            y_indices, x_indices = np.where(feat_mask)
            center_y = float(np.mean(y_indices))
            center_x = float(np.mean(x_indices))

            # Convert pixel coords to real-world offset
            lat_offset = ((height / 2.0) - center_y) * pixel_size_meters / meters_per_deg_lat
            lon_offset = (center_x - (width / 2.0)) * pixel_size_meters / meters_per_deg_lon

            area_sq_m = feat_pixels * (pixel_size_meters ** 2)
            mean_anomaly_z = float(np.mean(z_score_grid[feat_mask]))
            
            # Diagnose probable cause based on multi-index signatures
            has_re_collapse = bool(np.any(early_red_edge_stress[feat_mask]))
            severity_tag = "high" if mean_anomaly_z < -2.5 else "moderate"
            
            if has_re_collapse and severity_tag == "high":
                probable_cause = "Fungal Infection Hotspot / Canopy Necrosis"
                action_rec = "Deploy drone scout to coordinates for leaf inspection; prepare localized fungicide."
            elif water_index is not None and np.mean(water_index[feat_mask]) < 0.1:
                probable_cause = "Localized Moisture Stress / Drip Line Clog"
                action_rec = "Inspect irrigation zone nozzle pressure and soil moisture depth."
            else:
                probable_cause = "Vegetation Vigor Deficit / Nitrogen Deficiency"
                action_rec = "Verify variable-rate fertilizer coverage and scout for pest infestation."

            hotspots.append({
                "hotspot_id": int(feat_id),
                "latitude": round(origin_lat + lat_offset, 6),
                "longitude": round(origin_lon + lon_offset, 6),
                "area_m2": round(area_sq_m, 1),
                "area_ha": round(area_sq_m / 10000.0, 4),
                "severity": severity_tag,
                "mean_z_score": round(mean_anomaly_z, 2),
                "probable_cause": probable_cause,
                "recommended_action": action_rec,
                "pixel_count": feat_pixels
            })

        total_field_pixels = int(np.sum(valid_mask))
        total_anomaly_area_ha = (total_anomaly_pixels * (pixel_size_meters ** 2)) / 10000.0
        total_field_area_ha = (total_field_pixels * (pixel_size_meters ** 2)) / 10000.0
        anomaly_pct = round((total_anomaly_pixels / max(total_field_pixels, 1)) * 100.0, 2)

        return {
            "status": "success",
            "field_mean_index": round(mean_val, 3),
            "field_std_index": round(std_val, 3),
            "total_field_area_ha": round(total_field_area_ha, 2),
            "anomalous_area_ha": round(total_anomaly_area_ha, 3),
            "anomalous_area_pct": anomaly_pct,
            "anomaly_count": len(hotspots),
            "hotspots": sorted(hotspots, key=lambda x: x["area_m2"], reverse=True),
            "risk_assessment": "High Infection/Stress Alert" if anomaly_pct > 8.0 else ("Moderate Caution" if anomaly_pct > 3.0 else "Healthy & Homogeneous")
        }

"""
CropWatch Lite - Drone (UAV) Visible-Band Photogrammetry & Canopy Analysis
Extracts visible vegetation indices (VARI, GLI, ExG, TGI), canopy cover %,
diseased foliage patches, and precision spray maps from standard low-cost drone RGB imagery.
"""

import io
import base64
from typing import Dict, Any, Tuple, Optional
import numpy as np
from PIL import Image

from core.indices import SpectralIndices


class DronePipeline:
    """
    High-efficiency UAV processing engine for low-cost RGB photogrammetry.
    Allows consumer drones to perform sub-centimeter canopy segmentation and health mapping.
    """

    def __init__(self, canopy_exg_thresh: float = 0.05):
        self.canopy_exg_thresh = canopy_exg_thresh

    def process_orthomosaic_tile(
        self,
        image_input: Any,
        gsd_cm_per_pixel: float = 2.5,
        altitude_m: float = 60.0
    ) -> Dict[str, Any]:
        """
        Analyzes a drone RGB aerial image or orthomosaic slice:
        1. Computes visible-band indices (VARI, GLI, ExG, TGI).
        2. Calculates Canopy Cover % (Fraction of Ground Covered by Foliage).
        3. Identifies stressed / diseased canopy zones.
        4. Calculates localized spray volume requirements.
        """
        pil_img = self._to_pil_image(image_input)
        img_np = np.array(pil_img.convert("RGB"))
        h, w, _ = img_np.shape

        # Normalize RGB [0, 1]
        rgb_norm = img_np.astype(np.float32) / 255.0

        # 1. Compute Indices
        indices = SpectralIndices.compute_all_drone_rgb(rgb_norm)
        vari = indices["vari"]
        gli = indices["gli"]
        exg = indices["exg"]
        tgi = indices["tgi"]

        # 2. Segment Canopy (Vegetation vs Soil / Shadow / Non-Crop)
        canopy_mask = (exg > self.canopy_exg_thresh) & (vari > 0.0)
        total_pixels = h * w
        canopy_pixels = int(np.sum(canopy_mask))
        canopy_cover_pct = round((canopy_pixels / max(total_pixels, 1)) * 100.0, 2)

        # 3. Analyze Health Distribution inside Canopy
        canopy_vari = vari[canopy_mask]
        if len(canopy_vari) > 0:
            mean_vari = float(np.mean(canopy_vari))
            # Stressed canopy: VARI < 0.10 within green foliage
            stressed_mask = canopy_mask & (vari < 0.12)
            healthy_mask = canopy_mask & (vari >= 0.12)
            
            stressed_pixels = int(np.sum(stressed_mask))
            stressed_pct_of_canopy = round((stressed_pixels / max(canopy_pixels, 1)) * 100.0, 2)
            healthy_pct_of_canopy = round(100.0 - stressed_pct_of_canopy, 2)
        else:
            mean_vari = 0.0
            stressed_pct_of_canopy = 0.0
            healthy_pct_of_canopy = 0.0

        # Physical Ground Area Calculations
        pixel_area_m2 = (gsd_cm_per_pixel / 100.0) ** 2
        total_area_m2 = total_pixels * pixel_area_m2
        canopy_area_m2 = canopy_pixels * pixel_area_m2
        stressed_area_m2 = (stressed_pixels if len(canopy_vari) > 0 else 0) * pixel_area_m2

        # 4. Generate Variable-Rate Precision Spray Prescription
        # Standard full-blanket spray: 200 L/ha -> Variable rate applies only to stressed/infected zones
        full_field_spray_l = (total_area_m2 / 10000.0) * 200.0
        targeted_spray_l = (stressed_area_m2 / 10000.0) * 200.0 + (canopy_area_m2 / 10000.0) * 30.0 # light maintenance
        chemical_savings_pct = round(max(0.0, (1.0 - (targeted_spray_l / max(full_field_spray_l, 1e-4))) * 100.0), 1)

        # 5. Generate Heatmap Color Ramps
        vari_colored_b64 = self._render_index_heatmap(vari, canopy_mask)

        return {
            "resolution_px": f"{w}x{h}",
            "gsd_cm_px": gsd_cm_per_pixel,
            "flight_altitude_m": altitude_m,
            "total_scanned_area_m2": round(total_area_m2, 1),
            "canopy_area_m2": round(canopy_area_m2, 1),
            "canopy_coverage_percentage": canopy_cover_pct,
            "mean_canopy_vari": round(mean_vari, 3),
            "healthy_canopy_pct": healthy_pct_of_canopy,
            "stressed_infected_canopy_pct": stressed_pct_of_canopy,
            "precision_spray_advisory": {
                "conventional_spray_liters": round(full_field_spray_l, 1),
                "cropwatch_precision_spray_liters": round(targeted_spray_l, 1),
                "chemical_and_cost_savings_pct": chemical_savings_pct,
                "spray_recommendation": f"Variable-rate spot treatment targeting {round(stressed_area_m2, 1)} m² hotspot zones reduces chemical application by {chemical_savings_pct}%."
            },
            "heatmap_base64": vari_colored_b64
        }

    def _to_pil_image(self, image_input: Any) -> Image.Image:
        if isinstance(image_input, Image.Image):
            return image_input
        elif isinstance(image_input, np.ndarray):
            return Image.fromarray(image_input.astype(np.uint8))
        elif isinstance(image_input, (bytes, bytearray)):
            return Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, str):
            if image_input.startswith("data:image"):
                _, encoded = image_input.split(",", 1)
                return Image.open(io.BytesIO(base64.b64decode(encoded)))
            return Image.open(image_input)
        raise ValueError("Unsupported image input")

    def _render_index_heatmap(self, index_arr: np.ndarray, mask: np.ndarray) -> str:
        """Converts float index into high-contrast agricultural colormap (Red -> Yellow -> Emerald Green)."""
        h, w = index_arr.shape
        rgb_heatmap = np.zeros((h, w, 3), dtype=np.uint8)

        # Scale index from [-0.2, 0.6] to [0, 1]
        norm = np.clip((index_arr + 0.2) / 0.8, 0.0, 1.0)

        # Color ramp:
        # 0.0 - 0.5: Red (230, 40, 40) to Yellow (240, 210, 40)
        # 0.5 - 1.0: Yellow (240, 210, 40) to Deep Forest Green (20, 180, 60)
        low_seg = norm < 0.5
        t_low = norm[low_seg] * 2.0
        rgb_heatmap[low_seg, 0] = (230 + t_low * (240 - 230)).astype(np.uint8)
        rgb_heatmap[low_seg, 1] = (40 + t_low * (210 - 40)).astype(np.uint8)
        rgb_heatmap[low_seg, 2] = (40 + t_low * (40 - 40)).astype(np.uint8)

        high_seg = ~low_seg
        t_high = (norm[high_seg] - 0.5) * 2.0
        rgb_heatmap[high_seg, 0] = (240 + t_high * (20 - 240)).astype(np.uint8)
        rgb_heatmap[high_seg, 1] = (210 + t_high * (180 - 210)).astype(np.uint8)
        rgb_heatmap[high_seg, 2] = (40 + t_high * (60 - 40)).astype(np.uint8)

        # Non-canopy / soil dimmed
        non_canopy = ~mask
        rgb_heatmap[non_canopy] = (rgb_heatmap[non_canopy].astype(np.float32) * 0.35 + 40).astype(np.uint8)

        pil_res = Image.fromarray(rgb_heatmap)
        buffered = io.BytesIO()
        pil_res.save(buffered, format="JPEG", quality=85)
        return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"

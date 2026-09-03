"""
CropWatch Lite - Agro-Meteorological & Soil Integration Engine
Calculates Growing Degree Days (GDD), Vapor Pressure Deficit (VPD), cumulative moisture balance,
and parses soil profile indicators (SOC, pH, texture) for yield forecasting.
"""

from typing import Dict, Any, List
import numpy as np


class WeatherSoilEngine:
    """
    Computes agronomic climate indices and soil metrics that drive crop growth and yield potential.
    """

    # Base temperatures for key crops (°C)
    CROP_T_BASE = {
        "corn": 10.0,
        "maize": 10.0,
        "soybean": 10.0,
        "wheat": 0.0,
        "tomato": 10.0,
        "potato": 7.0,
        "grape": 10.0,
        "rice": 10.0
    }

    @classmethod
    def calculate_gdd(cls, t_max: np.ndarray, t_min: np.ndarray, crop: str = "corn", t_upper: float = 30.0) -> Dict[str, Any]:
        """
        Calculates daily and cumulative Growing Degree Days (GDD / AGDD).
        GDD = max(min((Tmax + Tmin)/2, Tupper) - Tbase, 0)
        """
        t_base = cls.CROP_T_BASE.get(crop.lower(), 10.0)
        t_max = np.asarray(t_max, dtype=np.float32)
        t_min = np.asarray(t_min, dtype=np.float32)

        # Cap max temperature to upper threshold (standard agronomic practice)
        t_max_adj = np.clip(t_max, t_base, t_upper)
        t_min_adj = np.clip(t_min, t_base, t_upper)

        t_mean = (t_max_adj + t_min_adj) / 2.0
        daily_gdd = np.maximum(t_mean - t_base, 0.0)
        cumulative_gdd = np.cumsum(daily_gdd)

        return {
            "daily_gdd": [round(float(v), 2) for v in daily_gdd],
            "cumulative_gdd": [round(float(v), 1) for v in cumulative_gdd],
            "total_accumulated_gdd": round(float(cumulative_gdd[-1]) if len(cumulative_gdd) > 0 else 0.0, 1),
            "t_base": t_base
        }

    @classmethod
    def calculate_vpd(cls, t_mean: np.ndarray, rh_mean: np.ndarray) -> np.ndarray:
        """
        Calculates Vapor Pressure Deficit (VPD in kPa).
        Saturated Vapor Pressure: es = 0.61078 * exp((17.27 * T) / (T + 237.3))
        Actual Vapor Pressure: ea = es * (RH / 100)
        VPD = es - ea
        High VPD (>2.0 kPa) causes stomatal closure and photosynthetic slowdown.
        """
        t = np.asarray(t_mean, dtype=np.float32)
        rh = np.asarray(rh_mean, dtype=np.float32)

        es = 0.61078 * np.exp((17.27 * t) / (t + 237.3))
        ea = es * (rh / 100.0)
        vpd = np.maximum(es - ea, 0.0)
        return vpd

    @classmethod
    def generate_season_weather_profile(
        cls,
        crop: str = "corn",
        days_in_season: int = 120,
        climate_scenario: str = "optimal"
    ) -> Dict[str, Any]:
        """
        Synthesizes a realistic daily agro-climatic timeseries (temperatures, rain, solar radiation, VPD)
        calibrated to crop phenological stages.
        """
        np.random.seed(101)
        days = np.arange(1, days_in_season + 1)

        # Base temperature curve (Bell-shaped curve peaking in mid-season)
        peak_day = days_in_season * 0.55
        temp_curve = 18.0 + 12.0 * np.exp(-((days - peak_day) ** 2) / (2 * (days_in_season * 0.3) ** 2))
        noise = np.random.normal(0, 2.5, days_in_season)
        t_mean = temp_curve + noise
        t_max = t_mean + np.random.uniform(4.0, 9.0, days_in_season)
        t_min = t_mean - np.random.uniform(4.0, 8.0, days_in_season)

        # Rainfall distribution
        rain_prob = 0.28 if climate_scenario == "optimal" else (0.12 if climate_scenario == "drought" else 0.45)
        rain_mask = np.random.rand(days_in_season) < rain_prob
        rain_mm = np.where(rain_mask, np.random.gamma(shape=2.5, scale=4.5, size=days_in_season), 0.0)

        # Humidity & VPD
        rh = np.clip(68.0 - (t_mean - 20.0) * 1.5 + (rain_mm > 0) * 20.0 + np.random.normal(0, 5, days_in_season), 25.0, 98.0)
        vpd = cls.calculate_vpd(t_mean, rh)

        # Solar Radiation (MJ/m2/day)
        solar_rad = np.clip(18.0 + 8.0 * np.sin(np.pi * days / days_in_season) - (rain_mm > 1.0) * 9.0 + np.random.normal(0, 2, days_in_season), 5.0, 32.0)

        gdd_res = cls.calculate_gdd(t_max, t_min, crop=crop)

        return {
            "days": days.tolist(),
            "t_max": [round(float(v), 1) for v in t_max],
            "t_min": [round(float(v), 1) for v in t_min],
            "t_mean": [round(float(v), 1) for v in t_mean],
            "precipitation_mm": [round(float(v), 1) for v in rain_mm],
            "cumulative_rain_mm": [round(float(v), 1) for v in np.cumsum(rain_mm)],
            "relative_humidity_pct": [round(float(v), 1) for v in rh],
            "vpd_kpa": [round(float(v), 2) for v in vpd],
            "solar_radiation_mj": [round(float(v), 1) for v in solar_rad],
            "gdd": gdd_res,
            "climate_summary": {
                "total_precipitation_mm": round(float(np.sum(rain_mm)), 1),
                "mean_temperature_c": round(float(np.mean(t_mean)), 1),
                "mean_vpd_kpa": round(float(np.mean(vpd)), 2),
                "total_gdd": gdd_res["total_accumulated_gdd"],
                "heat_stress_days_above_35c": int(np.sum(t_max >= 35.0))
            }
        }

    @classmethod
    def get_soil_profile(cls, soil_type: str = "clay_loam") -> Dict[str, Any]:
        """
        Returns typical agronomic soil physical and chemical parameters based on SoilGrids / USDA soil textures.
        """
        profiles = {
            "clay_loam": {
                "soil_type": "Clay Loam",
                "organic_carbon_pct": 2.4,
                "ph_level": 6.6,
                "clay_pct": 32.0,
                "sand_pct": 34.0,
                "silt_pct": 34.0,
                "cation_exchange_capacity_meq": 22.5,
                "available_water_capacity_mm_m": 165.0
            },
            "sandy_loam": {
                "soil_type": "Sandy Loam",
                "organic_carbon_pct": 1.5,
                "ph_level": 6.2,
                "clay_pct": 12.0,
                "sand_pct": 68.0,
                "silt_pct": 20.0,
                "cation_exchange_capacity_meq": 11.0,
                "available_water_capacity_mm_m": 110.0
            },
            "silt_loam": {
                "soil_type": "Silt Loam (Mollisol)",
                "organic_carbon_pct": 3.2,
                "ph_level": 6.8,
                "clay_pct": 18.0,
                "sand_pct": 22.0,
                "silt_pct": 60.0,
                "cation_exchange_capacity_meq": 26.0,
                "available_water_capacity_mm_m": 200.0
            }
        }
        return profiles.get(soil_type.lower(), profiles["clay_loam"])

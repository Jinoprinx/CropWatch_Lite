"""
CropWatch Lite - Drone Flight & Sensor Mission Planner (Mechanical & Aero Systems)
Computes Ground Sampling Distance (GSD), camera optics physics, flight line geometry,
battery endurance constraints, and precision spraying payload logistics for agricultural UAVs.
"""

from typing import Dict, Any, List
import numpy as np


class DroneFlightPlanner:
    """
    Agricultural Drone & Sensor Mission Planning Engine.
    Implements photogrammetry optics, flight kinematics, and spray payload calculations.
    """

    # Common sensor profiles
    CAMERA_PROFILES = {
        "dji_mavic_3e": {
            "name": "DJI Mavic 3 Enterprise (RGB)",
            "sensor_width_mm": 17.3,
            "sensor_height_mm": 13.0,
            "focal_length_mm": 12.3,
            "image_width_px": 5280,
            "image_height_px": 3956
        },
        "dji_mini_4_pro": {
            "name": "DJI Mini 4 Pro / Consumer RGB",
            "sensor_width_mm": 9.6,
            "sensor_height_mm": 7.2,
            "focal_length_mm": 6.72,
            "image_width_px": 4032,
            "image_height_px": 3024
        },
        "micasense_rededge_p": {
            "name": "MicaSense RedEdge-P (Multispectral)",
            "sensor_width_mm": 5.28,
            "sensor_height_mm": 3.96,
            "focal_length_mm": 5.5,
            "image_width_px": 2048,
            "image_height_px": 1536
        }
    }

    @classmethod
    def calculate_photogrammetry_mission(
        cls,
        field_area_ha: float = 25.0,
        camera_type: str = "dji_mavic_3e",
        flight_altitude_m: float = 60.0,
        forward_overlap_pct: float = 75.0,
        side_overlap_pct: float = 70.0,
        flight_speed_m_s: float = 7.5,
        battery_flight_time_min: float = 24.0
    ) -> Dict[str, Any]:
        """
        Calculates complete optical and flight kinematics for an aerial mapping mission.
        """
        cam = cls.CAMERA_PROFILES.get(camera_type.lower(), cls.CAMERA_PROFILES["dji_mavic_3e"])

        sensor_w = cam["sensor_width_mm"]
        sensor_h = cam["sensor_height_mm"]
        focal_l = cam["focal_length_mm"]
        img_w = cam["image_width_px"]
        img_h = cam["image_height_px"]

        # 1. Ground Sampling Distance (GSD) in cm/pixel
        # GSD_h = (Altitude_m * Sensor_W_mm * 100) / (Focal_mm * Img_W_px)
        gsd_h_cm = (flight_altitude_m * sensor_w * 100.0) / (focal_l * img_w)
        gsd_v_cm = (flight_altitude_m * sensor_h * 100.0) / (focal_l * img_h)
        gsd_cm = round(float((gsd_h_cm + gsd_v_cm) / 2.0), 2)

        # 2. Footprint on Ground per Single Image (meters)
        footprint_w_m = (flight_altitude_m * sensor_w) / focal_l
        footprint_h_m = (flight_altitude_m * sensor_h) / focal_l

        # 3. Distance Between Captures (Forward & Side Spacing)
        forward_spacing_m = footprint_h_m * (1.0 - (forward_overlap_pct / 100.0))
        side_spacing_m = footprint_w_m * (1.0 - (side_overlap_pct / 100.0))

        # 4. Field Geometry Approximation (Assuming roughly square field)
        field_area_m2 = field_area_ha * 10000.0
        field_side_length_m = np.sqrt(field_area_m2)

        # Number of flight pass lines
        num_flight_lines = int(np.ceil(field_side_length_m / max(side_spacing_m, 1.0)))
        total_flight_path_m = num_flight_lines * field_side_length_m + (num_flight_lines - 1) * side_spacing_m

        # Photos per line and total photos
        photos_per_line = int(np.ceil(field_side_length_m / max(forward_spacing_m, 1.0)))
        total_images_captured = num_flight_lines * photos_per_line

        # 5. Mission Flight Time (seconds & minutes)
        total_flight_time_sec = (total_flight_path_m / max(flight_speed_m_s, 0.1)) + (num_flight_lines * 10.0) # 10s turnaround per line
        total_flight_time_min = round(float(total_flight_time_sec / 60.0), 1)

        # Number of drone batteries required (assuming 20% safety margin)
        effective_battery_time = battery_flight_time_min * 0.80
        batteries_required = int(np.ceil(total_flight_time_min / max(effective_battery_time, 1.0)))

        # 6. Motion Blur Constraint (Max allowable shutter time)
        # Blur should not exceed 0.5 * GSD
        max_shutter_sec = (0.5 * (gsd_cm / 100.0)) / max(flight_speed_m_s, 0.1)

        return {
            "camera_model": cam["name"],
            "flight_altitude_m": flight_altitude_m,
            "gsd_cm_per_pixel": gsd_cm,
            "field_area_ha": field_area_ha,
            "ground_footprint_m": f"{round(footprint_w_m, 1)}m x {round(footprint_h_m, 1)}m",
            "forward_overlap_pct": forward_overlap_pct,
            "side_overlap_pct": side_overlap_pct,
            "flight_lines_count": num_flight_lines,
            "total_flight_distance_km": round(float(total_flight_path_m / 1000.0), 2),
            "estimated_flight_time_minutes": total_flight_time_min,
            "batteries_needed": batteries_required,
            "total_images_estimated": total_images_captured,
            "recommended_shutter_speed": f"1/{int(np.ceil(1.0 / max_shutter_sec))}s or faster",
            "survey_feasibility": "Optimal High-Precision Survey" if gsd_cm <= 3.5 else "Standard Regional Survey"
        }

    @classmethod
    def calculate_spray_drone_logistics(
        cls,
        target_spray_area_ha: float = 8.5,
        target_rate_liters_per_ha: float = 25.0, # Precision variable-rate
        spray_drone_tank_capacity_l: float = 20.0,
        flow_rate_l_min: float = 5.0,
        spray_swath_width_m: float = 5.0,
        flight_speed_m_s: float = 6.0
    ) -> Dict[str, Any]:
        """
        Calculates precision spray drone payload missions (e.g. DJI Agras T40 / T50 specs).
        """
        total_liquid_needed_liters = target_spray_area_ha * target_rate_liters_per_ha
        number_of_tank_refills = int(np.ceil(total_liquid_needed_liters / max(spray_drone_tank_capacity_l, 1.0)))

        # Application time
        total_spray_time_min = total_liquid_needed_liters / max(flow_rate_l_min, 0.1)
        # Turnaround and refill time (~4 min per tank)
        refill_downtime_min = (number_of_tank_refills - 1) * 4.0
        total_mission_time_min = round(float(total_spray_time_min + refill_downtime_min), 1)

        return {
            "target_spray_area_ha": target_spray_area_ha,
            "total_fungicide_mix_liters": round(float(total_liquid_needed_liters), 1),
            "tank_capacity_liters": spray_drone_tank_capacity_l,
            "required_tank_payload_refills": number_of_tank_refills,
            "active_spray_time_min": round(float(total_spray_time_min), 1),
            "total_field_application_time_min": total_mission_time_min,
            "swath_width_m": spray_swath_width_m
        }

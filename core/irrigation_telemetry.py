"""
CropWatch Lite - Smart Irrigation: IoT Telemetry Simulation Engine
Simulates an array of capacitive soil-moisture ESP32 sensor nodes wired to AWS IoT Core.
Each node tracks volumetric water content (VWC), soil temperature, electrical conductivity (EC),
battery level, and relay / solenoid valve state. Supports edge-fallback mode for cloud-offline resilience.
"""

import math
import random
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


# -----------------------------------------------------------------
# Data Structures
# -----------------------------------------------------------------

class SensorNode:
    """Represents a single capacitive ESP32 moisture sensor node in the field."""

    SOIL_TYPES = {
        "clay_loam":  {"drain_rate": 0.012, "fc_vwc": 0.38, "pwp_vwc": 0.18},
        "sandy_loam": {"drain_rate": 0.028, "fc_vwc": 0.26, "pwp_vwc": 0.10},
        "silt_loam":  {"drain_rate": 0.018, "fc_vwc": 0.42, "pwp_vwc": 0.16},
    }

    def __init__(
        self,
        node_id: str,
        zone_id: str,
        latitude: float,
        longitude: float,
        soil_type: str = "clay_loam",
        initial_vwc: Optional[float] = None,
    ):
        self.node_id = node_id
        self.zone_id = zone_id
        self.latitude = latitude
        self.longitude = longitude
        self.soil_type = soil_type
        self.soil_params = self.SOIL_TYPES.get(soil_type, self.SOIL_TYPES["clay_loam"])

        self._vwc = initial_vwc if initial_vwc is not None else random.uniform(0.25, 0.48)
        self._temp_c = random.uniform(18.0, 26.0)
        self._ec_ds_m = random.uniform(0.3, 1.2)
        self._battery_pct = random.uniform(72.0, 99.0)
        self._valve_open = False
        self._vwc_history: List[float] = [round(self._vwc * 100.0, 1)] * 288

    def tick(self, minutes_elapsed: float = 5.0) -> None:
        """Advance sensor state by minutes_elapsed."""
        params = self.soil_params
        et_loss = params["drain_rate"] * (minutes_elapsed / 60.0)
        self._vwc = max(params["pwp_vwc"], self._vwc - et_loss)
        if self._valve_open:
            self._vwc = min(params["fc_vwc"], self._vwc + 0.007)
        self._temp_c = max(10.0, min(40.0, self._temp_c + random.gauss(0, 0.3)))
        if self._valve_open:
            self._ec_ds_m = max(0.15, self._ec_ds_m - 0.02)
        else:
            self._ec_ds_m = min(3.5, self._ec_ds_m + 0.005)
        self._battery_pct = max(0.0, self._battery_pct - 0.001)
        self._vwc_history.pop(0)
        self._vwc_history.append(round(self._vwc * 100.0, 1))

    def as_telemetry_packet(self) -> Dict[str, Any]:
        vwc_pct = round(self._vwc * 100.0, 2)
        fc_pct = round(self.soil_params["fc_vwc"] * 100.0, 1)
        pwp_pct = round(self.soil_params["pwp_vwc"] * 100.0, 1)
        plant_avail = max(0.0, vwc_pct - pwp_pct)
        max_avail = max(0.01, fc_pct - pwp_pct)
        rel_sat = round(plant_avail / max_avail * 100.0, 1)
        ec_status = ("critical" if self._ec_ds_m > 2.5 else
                     "elevated" if self._ec_ds_m > 1.5 else "normal")
        return {
            "node_id": self.node_id,
            "zone_id": self.zone_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "location": {"lat": round(self.latitude, 6), "lon": round(self.longitude, 6)},
            "soil_type": self.soil_type,
            "vwc_pct": vwc_pct,
            "field_capacity_pct": fc_pct,
            "permanent_wilting_point_pct": pwp_pct,
            "relative_saturation_pct": rel_sat,
            "soil_temp_c": round(self._temp_c, 1),
            "ec_ds_m": round(self._ec_ds_m, 3),
            "ec_status": ec_status,
            "battery_pct": round(self._battery_pct, 1),
            "battery_status": "low" if self._battery_pct < 20.0 else "ok",
            "valve_open": self._valve_open,
            "status": _classify_vwc_status(vwc_pct, fc_pct, pwp_pct),
            "mqtt_topic": f"cropwatch/telemetry/{self.node_id}",
            "vwc_24h_trend": self._vwc_history[-12:],
        }

    def open_valve(self) -> None:
        self._valve_open = True

    def close_valve(self) -> None:
        self._valve_open = False

    @property
    def vwc_pct(self) -> float:
        return round(self._vwc * 100.0, 2)


class PumpSimulator:
    """Simulates a Variable Frequency Drive (VFD) centrifugal pump."""

    NOMINAL_FLOW_LPM = 420.0
    NOMINAL_PRESSURE_BAR = 4.5
    TARGET_PRESSURE_BAR = 3.5

    def __init__(self):
        self._speed_pct = 0.0

    def set_speed(self, speed_pct: float) -> None:
        self._speed_pct = max(0.0, min(100.0, speed_pct))

    def status(self) -> Dict[str, Any]:
        ratio = self._speed_pct / 100.0
        flow_lpm = round(self.NOMINAL_FLOW_LPM * ratio, 1)
        pressure_bar = round(self.NOMINAL_PRESSURE_BAR * (ratio ** 2), 2)
        power_kw = round(7.5 * (ratio ** 3), 2)
        efficiency = round(max(0.0, 1.0 - abs(ratio - 0.75) * 0.8) * 100.0, 1)
        return {
            "running": self._speed_pct > 0.0,
            "speed_pct": round(self._speed_pct, 1),
            "flow_lpm": flow_lpm,
            "pressure_bar": pressure_bar,
            "power_kw": power_kw,
            "efficiency_pct": efficiency,
            "status": "running" if self._speed_pct > 0 else "standby",
        }

    def compute_optimal_speed(self, active_zones: int,
                              emitter_flow_lph: float = 8.0,
                              emitters_per_zone: int = 120) -> float:
        """Calculate VFD speed (%) to maintain TARGET_PRESSURE_BAR."""
        if active_zones == 0:
            return 0.0
        total_flow_lpm = (emitter_flow_lph * emitters_per_zone * active_zones) / 60.0
        speed_ratio = math.sqrt(max(0.0, self.TARGET_PRESSURE_BAR / self.NOMINAL_PRESSURE_BAR))
        flow_ratio = total_flow_lpm / self.NOMINAL_FLOW_LPM
        speed_pct = max(speed_ratio, flow_ratio) * 100.0
        return round(min(speed_pct, 100.0), 1)


# -----------------------------------------------------------------
# Main Telemetry Engine
# -----------------------------------------------------------------

class IrrigationTelemetry:
    """
    Simulates the full in-field IoT sensor network for Smart Irrigation.
    Acts as a local proxy for the AWS IoT Core MQTT broker.
    """

    ZONE_NODE_LAYOUT = [
        ("zone_nw", "n1", +0.002, -0.003, "silt_loam"),
        ("zone_nw", "n2", +0.003, -0.001, "silt_loam"),
        ("zone_ne", "n3", +0.002, +0.001, "clay_loam"),
        ("zone_ne", "n4", +0.003, +0.003, "clay_loam"),
        ("zone_sw", "n5", -0.001, -0.003, "sandy_loam"),
        ("zone_sw", "n6", -0.002, -0.001, "sandy_loam"),
        ("zone_se", "n7", -0.001, +0.001, "clay_loam"),
        ("zone_se", "n8", -0.002, +0.003, "clay_loam"),
    ]

    def __init__(self, origin_lat: float = 42.021, origin_lon: float = -93.646, seed: int = 77):
        random.seed(seed)
        self.origin_lat = origin_lat
        self.origin_lon = origin_lon
        self._nodes: Dict[str, SensorNode] = {}
        self._pump = PumpSimulator()
        self._cloud_connected = True
        self._edge_fallback_active = False
        self._fallback_log: List[Dict[str, Any]] = []

    def generate_field_sensor_network(self, field_id: str,
                                      base_vwc_pct: Optional[float] = None) -> List[Dict[str, Any]]:
        """Instantiates 8 virtual ESP32 sensor nodes. Returns sensor registry."""
        self._nodes.clear()
        registry = []
        zone_defaults = {"zone_sw": 0.22, "zone_se": 0.30, "zone_ne": 0.42, "zone_nw": 0.46}

        for zone_id, suffix, dlat, dlon, soil_type in self.ZONE_NODE_LAYOUT:
            if base_vwc_pct is not None:
                init_vwc = (base_vwc_pct / 100.0) + random.gauss(0, 0.04)
            else:
                init_vwc = zone_defaults.get(zone_id, 0.35) + random.gauss(0, 0.03)

            node_id = f"{field_id}_{zone_id}_{suffix}"
            node = SensorNode(
                node_id=node_id,
                zone_id=zone_id,
                latitude=self.origin_lat + dlat,
                longitude=self.origin_lon + dlon,
                soil_type=soil_type,
                initial_vwc=max(0.05, init_vwc),
            )
            self._nodes[node_id] = node
            registry.append({
                "node_id": node_id,
                "zone_id": zone_id,
                "lat": node.latitude,
                "lon": node.longitude,
                "soil_type": soil_type,
            })
        return registry

    def stream_all_telemetry(self, advance_minutes: float = 5.0) -> List[Dict[str, Any]]:
        """Advance all nodes and return updated telemetry packets."""
        for node in self._nodes.values():
            node.tick(minutes_elapsed=advance_minutes)
        return [n.as_telemetry_packet() for n in self._nodes.values()]

    def get_current_telemetry(self) -> List[Dict[str, Any]]:
        """Return current telemetry without advancing time."""
        return [n.as_telemetry_packet() for n in self._nodes.values()]

    def get_zone_summary(self) -> Dict[str, Dict[str, Any]]:
        """Aggregate mean/min/max VWC and valve state per zone."""
        zones: Dict[str, List[SensorNode]] = {}
        for node in self._nodes.values():
            zones.setdefault(node.zone_id, []).append(node)

        summary = {}
        for zone_id, nodes in zones.items():
            vwc_vals = [n.vwc_pct for n in nodes]
            summary[zone_id] = {
                "zone_id": zone_id,
                "node_count": len(nodes),
                "mean_vwc_pct": round(sum(vwc_vals) / len(vwc_vals), 2),
                "min_vwc_pct": round(min(vwc_vals), 2),
                "max_vwc_pct": round(max(vwc_vals), 2),
                "any_valve_open": any(n._valve_open for n in nodes),
                "ec_ds_m_mean": round(sum(n._ec_ds_m for n in nodes) / len(nodes), 3),
            }
        return summary

    def simulate_relay_command(self, zone_id: str, open_valve: bool) -> Dict[str, Any]:
        """Send open/close command to all nodes in a zone."""
        affected = [n for n in self._nodes.values() if n.zone_id == zone_id]
        if not affected:
            return {"success": False, "error": f"Zone {zone_id} not found"}
        for node in affected:
            node.open_valve() if open_valve else node.close_valve()
        return {
            "success": True,
            "zone_id": zone_id,
            "command": "open" if open_valve else "close",
            "nodes_commanded": [n.node_id for n in affected],
            "mqtt_topic": f"cropwatch/commands/{zone_id}",
            "ack_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    def get_pump_status(self) -> Dict[str, Any]:
        """Return VFD pump telemetry with auto-speed calculation."""
        active_zones = len({n.zone_id for n in self._nodes.values() if n._valve_open})
        optimal = self._pump.compute_optimal_speed(active_zones)
        self._pump.set_speed(optimal)
        status = self._pump.status()
        status["active_irrigation_zones"] = active_zones
        status["target_pressure_bar"] = PumpSimulator.TARGET_PRESSURE_BAR
        return status

    def detect_drip_clog(self) -> List[Dict[str, Any]]:
        """Flag nodes with very low VWC while zone valve is open and neighbours are wet."""
        alerts = []
        zone_nodes: Dict[str, List[SensorNode]] = {}
        for node in self._nodes.values():
            zone_nodes.setdefault(node.zone_id, []).append(node)
        for zone_id, nodes in zone_nodes.items():
            if not any(n._valve_open for n in nodes):
                continue
            for node in nodes:
                others = [n.vwc_pct for n in nodes if n.node_id != node.node_id]
                if node.vwc_pct < 15.0 and others and min(others) >= 28.0:
                    alerts.append({
                        "alert_type": "drip_clog",
                        "severity": "high",
                        "node_id": node.node_id,
                        "zone_id": zone_id,
                        "node_vwc_pct": node.vwc_pct,
                        "zone_mean_vwc_pct": round(sum(n.vwc_pct for n in nodes) / len(nodes), 2),
                        "message": (f"Probable emitter clog at {node.node_id}. "
                                    f"VWC={node.vwc_pct}% while neighbours >= {min(others):.1f}%."),
                        "recommended_action": "Inspect and flush drip emitters at node GPS coordinates.",
                    })
        return alerts

    def activate_edge_fallback(self, vwc_threshold_pct: float = 28.0) -> Dict[str, Any]:
        """Activate cloud-offline fallback: threshold-based valve decisions."""
        self._cloud_connected = False
        self._edge_fallback_active = True
        actions = []
        for zone_id, summary in self.get_zone_summary().items():
            needs_water = summary["min_vwc_pct"] < vwc_threshold_pct
            action = {
                "zone_id": zone_id,
                "trigger": "vwc_below_threshold",
                "min_vwc_pct": summary["min_vwc_pct"],
                "threshold_pct": vwc_threshold_pct,
                "action": "open_valve_20min" if needs_water else "no_action",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "mode": "edge_fallback",
            }
            if needs_water:
                self.simulate_relay_command(zone_id, open_valve=True)
            actions.append(action)
            self._fallback_log.append(action)

        return {
            "mode": "edge_fallback",
            "cloud_connected": False,
            "vwc_threshold_pct": vwc_threshold_pct,
            "zones_evaluated": len(actions),
            "zones_irrigating": sum(1 for a in actions if "open" in a["action"]),
            "actions": actions,
        }

    def restore_cloud_connection(self) -> Dict[str, Any]:
        """Restore cloud connectivity and return log for DynamoDB sync."""
        self._cloud_connected = True
        self._edge_fallback_active = False
        log = list(self._fallback_log)
        self._fallback_log.clear()
        return {"mode": "cloud_connected", "cloud_connected": True, "synced_fallback_actions": log}

    def get_fallback_log(self) -> List[Dict[str, Any]]:
        return self._fallback_log[-10:]

    @property
    def is_cloud_connected(self) -> bool:
        return self._cloud_connected

    @property
    def is_edge_fallback_active(self) -> bool:
        return self._edge_fallback_active


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

def _classify_vwc_status(vwc_pct: float, fc_pct: float, pwp_pct: float) -> str:
    if vwc_pct >= fc_pct * 0.90:
        return "saturated"
    if vwc_pct >= fc_pct * 0.65:
        return "optimal"
    if vwc_pct >= (fc_pct + pwp_pct) / 2.0:
        return "moderate_deficit"
    if vwc_pct >= pwp_pct + 5.0:
        return "critical_deficit"
    return "at_wilting_point"

"""
CropWatch Lite - Smart Irrigation: Edge Fallback Controller
Standalone Python script that operates the irrigation system autonomously
when cloud connectivity (AWS IoT Core) is unavailable. Reads sensor state
from a local JSON registry, applies simple VWC threshold rules, and logs all
irrigation decisions for DynamoDB sync on cloud reconnect.

Usage:
    python controller.py --crop corn --field_id field_corn_01 [--once]

    --once   Run a single evaluation and exit (default: continuous loop every 30 min)
"""

import json
import os
import time
import argparse
import random
from datetime import datetime, timezone

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
LOG_PATH = os.path.join(os.path.dirname(__file__), "irrigation_log.json")
SENSOR_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "sensor_registry.json")


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def load_log() -> list:
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r") as f:
            return json.load(f)
    return []


def save_log(entries: list, max_entries: int = 500) -> None:
    entries = entries[-max_entries:]
    with open(LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def read_sensor_vwc(zone_id: str, config: dict) -> float:
    """
    Reads VWC from the local sensor registry file.
    In production, this would read from an attached ADC (e.g., I2C multiplexer)
    or from a locally-cached MQTT message queue.
    Falls back to simulated values for demo purposes.
    """
    if os.path.exists(SENSOR_REGISTRY_PATH):
        with open(SENSOR_REGISTRY_PATH, "r") as f:
            registry = json.load(f)
        zone_data = registry.get(zone_id, {})
        return float(zone_data.get("mean_vwc_pct", 35.0))

    # Demo simulation: zone_sw is driest (sandy soil)
    base = {"zone_sw": 21.0, "zone_se": 29.0, "zone_ne": 40.0, "zone_nw": 44.0}
    return base.get(zone_id, 33.0) + random.gauss(0, 2.0)


def open_valve(zone_id: str, gpio: int, duration_min: float) -> None:
    """
    Open the solenoid valve for a zone by asserting the relay GPIO pin.
    In production: import RPi.GPIO or use MicroPython machine.Pin on ESP32.
    """
    print(f"  [RELAY] GPIO {gpio} HIGH  → Zone {zone_id} valve OPEN  ({duration_min:.0f} min)")
    # time.sleep(duration_min * 60)   # Uncomment on real hardware
    print(f"  [RELAY] GPIO {gpio} LOW   → Zone {zone_id} valve CLOSED")


def run_evaluation_cycle(crop: str, field_id: str, config: dict) -> list:
    """Run one irrigation evaluation and return list of action log entries."""
    crop_thresh = config["crop_thresholds"].get(crop, config["crop_thresholds"]["corn"])
    critical_vwc = crop_thresh["critical_vwc_pct"]
    duration_min = config["default_valve_open_duration_min"]
    actions = []

    print(f"\n{'='*60}")
    print(f"CropWatch Edge Fallback | {datetime.now(timezone.utc).isoformat()}")
    print(f"Field: {field_id}  |  Crop: {crop}  |  Threshold: {critical_vwc}% VWC")
    print(f"{'='*60}")

    for zone_cfg in config["zones"]:
        zone_id = zone_cfg["zone_id"]
        gpio    = zone_cfg["valve_gpio"]
        vwc     = read_sensor_vwc(zone_id, config)
        needs_water = vwc < critical_vwc

        status = "IRRIGATE" if needs_water else "SKIP"
        print(f"  Zone {zone_id:8s} | VWC={vwc:5.1f}%  (threshold={critical_vwc}%)  → {status}")

        entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "field_id": field_id,
            "zone_id": zone_id,
            "vwc_pct": round(vwc, 1),
            "threshold_pct": critical_vwc,
            "action": "irrigate" if needs_water else "skip",
            "duration_min": duration_min if needs_water else 0,
            "mode": "edge_fallback",
            "synced_to_cloud": False,
        }
        actions.append(entry)

        if needs_water:
            open_valve(zone_id, gpio, duration_min)

    return actions


def sync_to_dynamodb(log_entries: list) -> None:
    """
    Stub: on cloud reconnect, push unsynced log entries to DynamoDB.
    In production: use boto3.resource("dynamodb").Table("CropWatch-IrrigationLog").put_item(...)
    """
    unsynced = [e for e in log_entries if not e.get("synced_to_cloud", False)]
    if not unsynced:
        return
    print(f"\n[SYNC] Would push {len(unsynced)} fallback entries to DynamoDB (stub).")
    for entry in unsynced:
        entry["synced_to_cloud"] = True


def main():
    parser = argparse.ArgumentParser(description="CropWatch Lite Edge Fallback Controller")
    parser.add_argument("--crop", default="corn", help="Crop type")
    parser.add_argument("--field_id", default="field_corn_01", help="Field identifier")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    config = load_config()
    interval_s = config["check_interval_minutes"] * 60

    print(f"CropWatch Lite | Edge Fallback Controller")
    print(f"Crop: {args.crop}  |  Field: {args.field_id}")
    print(f"Mode: {'single-shot' if args.once else f'continuous ({config[\"check_interval_minutes\"]} min interval)'}")

    log_entries = load_log()

    while True:
        new_actions = run_evaluation_cycle(args.crop, args.field_id, config)
        log_entries.extend(new_actions)
        save_log(log_entries, max_entries=config["max_log_entries"])
        print(f"\n  [LOG] {len(new_actions)} actions logged ({LOG_PATH})")

        if args.once:
            break
        print(f"\n  Sleeping {config['check_interval_minutes']} minutes until next check...")
        time.sleep(interval_s)


if __name__ == "__main__":
    main()

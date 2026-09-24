try:
    import requests as _requests
except ImportError:
    _requests = None
import urllib.request
import urllib.error
import gzip
import json
import math
import time
import logging
import threading
import concurrent.futures
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Any, List, Optional

from app.config import settings
from app.ml.model_loader import get_ml_manager

logger = logging.getLogger("cow_logger.aws_service")

# Activity metadata mapping
ACTIVITY_MAP = {
    "RES": {"code": "RES", "name": "Standing Rest", "color": "#64748b", "icon": "fa-pause", "category": "Normal"},
    "RUS": {"code": "RUS", "name": "Ruminating", "color": "#06b6d4", "icon": "fa-arrows-spin", "category": "Normal"},
    "MOV": {"code": "MOV", "name": "Walking / Moving", "color": "#f59e0b", "icon": "fa-person-walking", "category": "Active"},
    "FEP": {"code": "FEP", "name": "Feeding", "color": "#10b981", "icon": "fa-bowl-food", "category": "Normal"},
    "FED": {"code": "FEP", "name": "Feeding", "color": "#10b981", "icon": "fa-bowl-food", "category": "Normal"},
    "DRN": {"code": "DRN", "name": "Drinking Water", "color": "#3b82f6", "icon": "fa-glass-water", "category": "Normal"},
    "LCK": {"code": "LCK", "name": "Licking", "color": "#ec4899", "icon": "fa-hand-sparkles", "category": "Normal"},
    "REL": {"code": "REL", "name": "Lying Rest", "color": "#8b5cf6", "icon": "fa-bed", "category": "Normal"},
    "URI": {"code": "URI", "name": "Urinating", "color": "#eab308", "icon": "fa-droplet", "category": "Normal"},
    "DEF": {"code": "DEF", "name": "Defecating", "color": "#a16207", "icon": "fa-circle-dot", "category": "Normal"},
    "ATT": {"code": "ATT", "name": "Aggressive / Attacking", "color": "#ef4444", "icon": "fa-triangle-exclamation", "category": "Active"},
    "GRZ": {"code": "FEP", "name": "Grazing Field", "color": "#10b981", "icon": "fa-bowl-food", "category": "Normal"},
    "ETC": {"code": "ETC", "name": "Other Activity", "color": "#94a3b8", "icon": "fa-ellipsis", "category": "Other"}
}

import os

# AWS CowNeck Collar transmits 1 telemetry packet per 60 seconds (1 minute).
# 1 packet represents 60.0 seconds of livestock behavioral observation.
AWS_PACKET_INTERVAL_SECONDS = 60.0

# Persistent Last-Known-Good caches so AWS data NEVER vanishes on timeouts or restarts
SNAPSHOT_FILE = os.path.join(os.path.dirname(__file__), ".aws_telemetry_snapshot.json")
_LAST_VALID_DASHBOARD: Dict[str, Any] = {}
_LAST_VALID_7DAY: Dict[str, Any] = {}
_LAST_VALID_LOGS: Dict[str, Any] = {}
_AWS_DAILY_SUMMARIES: Dict[str, Dict[str, dict]] = {}  # {device_id: {date_str_yyyy_mm_dd: summary_dict}}
_LAST_KNOWN_TELEMETRY: Dict[str, dict] = {}  # {device_id: {telemetry, accelBuffer, timestamp}}

def _save_snapshot():
    try:
        data = {
            "dashboard": _LAST_VALID_DASHBOARD,
            "daily_summaries": _AWS_DAILY_SUMMARIES,
            "logs": _LAST_VALID_LOGS,
            "last_known_telemetry": _LAST_KNOWN_TELEMETRY
        }
        with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f"Error saving AWS telemetry snapshot: {e}")

def _load_snapshot():
    global _LAST_VALID_DASHBOARD, _LAST_VALID_7DAY, _LAST_VALID_LOGS, _AWS_CACHE, _AWS_DAILY_SUMMARIES, _LAST_KNOWN_TELEMETRY
    if not os.path.exists(SNAPSHOT_FILE):
        return
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            _LAST_VALID_DASHBOARD.update(data.get("dashboard", {}))
            _LAST_VALID_LOGS.update(data.get("logs", {}))
            _LAST_KNOWN_TELEMETRY.update(data.get("last_known_telemetry", {}))

            # Load daily summaries (device_id -> date_str -> summary)
            saved_daily = data.get("daily_summaries", {})
            for dev_id, d_map in saved_daily.items():
                if dev_id not in _AWS_DAILY_SUMMARIES:
                    _AWS_DAILY_SUMMARIES[dev_id] = {}
                _AWS_DAILY_SUMMARIES[dev_id].update(d_map)

            # Migration: Extract per-day summaries from historical seven_day data
            old_7day = data.get("seven_day", {})
            for dev_id, s7 in old_7day.items():
                if dev_id not in _AWS_DAILY_SUMMARIES:
                    _AWS_DAILY_SUMMARIES[dev_id] = {}
                dates = s7.get("dates", [])
                rums = s7.get("ruminationHours", [])
                lyings = s7.get("lyingRestHours", [])
                feeds = s7.get("feedingHours", [])
                acts = s7.get("activeHours", [])
                mons = s7.get("monitoredHours", [])
                scores = s7.get("healthScores", [])
                estrus = s7.get("estrusIndices", [])
                for i, d_str in enumerate(dates):
                    if d_str not in _AWS_DAILY_SUMMARIES[dev_id]:
                        _AWS_DAILY_SUMMARIES[dev_id][d_str] = {
                            "monitored_hours": mons[i] if i < len(mons) else 0.0,
                            "rum_hours": rums[i] if i < len(rums) else 0.0,
                            "lying_hours": lyings[i] if i < len(lyings) else 0.0,
                            "feed_hours": feeds[i] if i < len(feeds) else 0.0,
                            "move_hours": acts[i] if i < len(acts) else 0.0,
                            "health_score": scores[i] if i < len(scores) else 0,
                            "estrus_index": estrus[i] if i < len(estrus) else 0,
                            "heat_count": 0,
                            "total_packets": int((mons[i] * 3600.0) / AWS_PACKET_INTERVAL_SECONDS) if i < len(mons) else 0
                        }

            # Cache last known telemetry from saved dashboard if not present
            for dev_id, dash in _LAST_VALID_DASHBOARD.items():
                if dev_id not in _LAST_KNOWN_TELEMETRY and dash.get("liveTelemetry"):
                    _LAST_KNOWN_TELEMETRY[dev_id] = {
                        "telemetry": dash["liveTelemetry"],
                        "accelBuffer": dash.get("accelBuffer"),
                        "timestamp": dash.get("liveTelemetry", {}).get("timestamp")
                    }

            # Sanitize loaded dashboard against current day to prevent yesterday's data leaking into today
            today_utc = datetime.now(timezone.utc).date()
            for dev_id, dash in list(_LAST_VALID_DASHBOARD.items()):
                last_seen = dash.get("liveTelemetry", {}).get("timestamp")
                is_today = False
                if last_seen:
                    try:
                        dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                        if dt.date() == today_utc:
                            is_today = True
                    except Exception:
                        pass
                if not is_today:
                    dash["isStale"] = True
                    dash["currentActivity"] = {
                        "code": None,
                        "name": "No Recent Data",
                        "color": "#64748b",
                        "icon": "fa-pause"
                    }
                    if "healthStatus" in dash:
                        dash["healthStatus"].update({
                            "monitoredHoursToday": 0.0,
                            "ruminationHoursToday": 0.0,
                            "lyingHoursToday": 0.0,
                            "feedingHoursToday": 0.0,
                            "movingHoursToday": 0.0,
                            "ruminationScore": 0,
                            "estrusProbabilityPercent": 0,
                            "isHeatDetected": False,
                            "healthRecommendation": "WARNING: No sensor data received today. Check collar node battery and uplink connectivity.",
                            "health_risk_decision": "NO_DATA"
                        })
                    if "ml_inference" in dash:
                        dash["ml_inference"].update({
                            "ml_engine_status": "OFFLINE",
                            "activity": {"code": None, "confidence": 0.0},
                            "heat_detection": {"in_heat": False, "heat_probability": 0.0, "alert_level": "NORMAL"},
                            "anomaly_detection": {"is_anomaly": False, "score": 0.0},
                            "health_risk_decision": "NO_DATA"
                        })

            # Pre-warm fast in-memory activity logs cache from snapshot
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for dev_id, saved_logs_data in _LAST_VALID_LOGS.items():
                l_list = saved_logs_data.get("logs", []) if isinstance(saved_logs_data, dict) else saved_logs_data
                if l_list:
                    act_cache_key = f"actlogs_{dev_id}_{today_str}"
                    _AWS_CACHE[act_cache_key] = {"expires_at": time.time() + 86400.0, "data": l_list}

        logger.info(f"Loaded persistent AWS telemetry snapshot with {len(_AWS_DAILY_SUMMARIES)} daily summary devices.")
    except Exception as e:
        logger.warning(f"Error loading AWS telemetry snapshot: {e}")

# In-memory caches for high-speed API performance
_AWS_CACHE: Dict[str, Dict[str, Any]] = {}
_HERD_ITEMS_CACHE: Dict[str, Any] = {"expires_at": 0.0, "data": []}
_METADATA_CACHE: Dict[str, Dict[str, Any]] = {}
_ML_PREDICTION_CACHE: Dict[str, Any] = {}
_HERD_IS_REFRESHING = False
_REFRESH_THREAD_LOCK = threading.Lock()
_TAGS_LOADED_AT = 0.0
CACHE_TTL_SECONDS = 300

# Per-device locks to coalesce concurrent in-flight requests and prevent duplicate AWS calls
_IN_FLIGHT_DEVICE_LOCKS: Dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()

def _get_device_lock(dev_id: str) -> threading.Lock:
    with _GLOBAL_LOCK:
        dev_key = str(dev_id).strip()
        if dev_key not in _IN_FLIGHT_DEVICE_LOCKS:
            _IN_FLIGHT_DEVICE_LOCKS[dev_key] = threading.Lock()
        return _IN_FLIGHT_DEVICE_LOCKS[dev_key]

# Load persistent snapshot immediately on module load
_load_snapshot()


def _parse_timestamp(pkt: dict) -> datetime:
    """Parse packet timestamp from Epoch or TimeStamp string."""
    epoch = pkt.get("Epoch")
    if epoch:
        try:
            return datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        except Exception:
            pass

    ts_str = pkt.get("TimeStamp", "")
    if ts_str:
        # e.g. "2026-09-22 16:49:56 IST"
        clean_str = ts_str.replace(" IST", "").strip()
        try:
            dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
            # IST is UTC + 5:30
            dt = dt.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

    return datetime.now(timezone.utc)


class AwsTelemetryService:
    @staticmethod
    def fetch_aws_raw(device_id: str, start_date: str = None, end_date: str = None) -> List[dict]:
        """
        Fetch raw packets from AWS Lambda CowNeck_API_Function.
        Handles gzip decompression, timeouts, and network errors.
        - Past days: 6s timeout, empty results cached 24h (no repeated timeouts).
        - Today: 10s timeout, results cached 5min.
        """
        now = datetime.now(timezone.utc)
        
        # Target specific date for 24 hours (startdate=target&enddate=target)
        if start_date and not end_date:
            resolved_start = start_date.strip()
            resolved_end = start_date.strip()
        elif end_date and not start_date:
            resolved_start = end_date.strip()
            resolved_end = end_date.strip()
        elif start_date and end_date:
            resolved_start = start_date.strip()
            resolved_end = end_date.strip()
        else:
            # Default for 24-hour telemetry: target today's date
            today_str = now.strftime("%d-%m-%Y")
            resolved_start = today_str
            resolved_end = today_str

        # AWS Lambda CowNeck_API_Function requires startdate == enddate (single day).
        # Multi-day ranges throw HTTP 500. Automatically fetch each day individually and combine.
        if resolved_start != resolved_end:
            try:
                s_dt = datetime.strptime(resolved_start, "%d-%m-%Y").date()
                e_dt = datetime.strptime(resolved_end, "%d-%m-%Y").date()
                if s_dt > e_dt:
                    s_dt, e_dt = e_dt, s_dt
                combined = []
                cur = s_dt
                while cur <= e_dt:
                    d_str = cur.strftime("%d-%m-%Y")
                    day_pkts = AwsTelemetryService.fetch_aws_raw(device_id, start_date=d_str, end_date=d_str)
                    combined.extend(day_pkts)
                    cur += timedelta(days=1)
                return combined
            except Exception as e:
                logger.warning(f"Error expanding multi-day range {resolved_start}..{resolved_end}: {e}")

        cache_key = f"raw_{device_id}_{resolved_start}_{resolved_end}"
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"]

        url = f"{settings.AWS_COWNECK_API_URL}?deviceid={device_id}&startdate={resolved_start}&enddate={resolved_end}"

        # Give AWS Lambda functions sufficient timeout to cold-start without throwing false Read timed out
        today_str = now.strftime("%d-%m-%Y")
        is_today = (resolved_start == today_str)
        read_timeout = 15 if is_today else 10

        try:
            if _requests is not None:
                resp = _requests.get(
                    url,
                    headers={"User-Agent": "CowMonitoring-Backend/1.0"},
                    timeout=(5, read_timeout),  # (connect_timeout, read_timeout)
                    stream=False
                )
                resp.raise_for_status()
                raw_bytes = resp.content
            else:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "CowMonitoring-Backend/1.0"}
                )
                with urllib.request.urlopen(req, timeout=read_timeout) as resp:
                    raw_bytes = resp.read()
            try:
                raw_bytes = gzip.decompress(raw_bytes)
            except Exception:
                pass

            payload = json.loads(raw_bytes.decode("utf-8"))
            packets = payload.get("Data", [])

            # Sort packets chronologically ascending
            packets.sort(key=lambda p: int(p.get("Epoch", 0)))

            # Cache past days for 24h — historical data never changes
            ttl = CACHE_TTL_SECONDS if is_today else 86400
            _AWS_CACHE[cache_key] = {
                "expires_at": time.time() + ttl,
                "data": packets
            }
            return packets
        except Exception as e:
            logger.warning(f"AWS API fetch for device {device_id} date {resolved_start}: {e}")
            if cached:
                return cached["data"]
            # Cache failure only briefly (30s) so transient network spikes/cold starts can be retried
            _AWS_CACHE[cache_key] = {
                "expires_at": time.time() + 30.0,
                "data": []
            }
            return []

    @classmethod
    def get_processed_packets(cls, device_id: str, start_date: str = None, end_date: str = None) -> List[dict]:
        """
        Fetches AWS packets and runs ML inference on each 80-sample window.
        Returns a list of parsed packets with their full ML inference results.
        Uses in-memory ML inference memoization to eliminate repeated calculations.
        """
        cache_key = f"processed_{device_id}_{start_date}_{end_date}"
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"]

        with _get_device_lock(str(device_id).strip()):
            # Re-check cache after acquiring lock
            cached = _AWS_CACHE.get(cache_key)
            if cached and cached["expires_at"] > time.time():
                return cached["data"]

            raw_packets = cls.fetch_aws_raw(device_id, start_date=start_date, end_date=end_date)
            if not raw_packets:
                return []

            manager = get_ml_manager()
            processed = []

            for pkt in raw_packets:
                raw_pts = pkt.get("Data", [])
                if len(raw_pts) < 3:
                    continue

                dt = _parse_timestamp(pkt)
                epoch_val = int(pkt.get("Epoch", dt.timestamp()))
                pred_cache_key = f"{device_id}_{epoch_val}_{len(raw_pts)}"

                x_buf = [float(raw_pts[j]) for j in range(0, len(raw_pts), 3)]
                y_buf = [float(raw_pts[j+1]) for j in range(0, len(raw_pts), 3)]
                z_buf = [float(raw_pts[j+2]) for j in range(0, len(raw_pts), 3)]

                # Check ML prediction memoization cache
                if pred_cache_key in _ML_PREDICTION_CACHE:
                    pred = _ML_PREDICTION_CACHE[pred_cache_key]
                else:
                    pred = manager.predict(x_buf, y_buf, z_buf)
                    _ML_PREDICTION_CACHE[pred_cache_key] = pred

                processed.append({
                    "device_id": str(device_id),
                    "timestamp": dt,
                    "epoch": epoch_val,
                    "x_buf": x_buf,
                    "y_buf": y_buf,
                    "z_buf": z_buf,
                    "ml_inference": pred
                })

            _AWS_CACHE[cache_key] = {
                "expires_at": time.time() + CACHE_TTL_SECONDS,
                "data": processed
            }
            return processed

    @classmethod
    def clear_cache(cls):
        """Clears metadata and herd caches for tag updates without wiping telemetry."""
        global _HERD_ITEMS_CACHE, _METADATA_CACHE, _TAGS_LOADED_AT
        _HERD_ITEMS_CACHE = {"expires_at": 0.0, "data": []}
        _METADATA_CACHE.clear()
        _TAGS_LOADED_AT = 0.0
        logger.info("Cleared AWS metadata & herd caches.")

    @classmethod
    def clear_all_telemetry_cache(cls):
        """Forces immediate wipe of telemetry caches and snapshots for fresh calculation."""
        global _AWS_CACHE, _LAST_VALID_DASHBOARD, _LAST_VALID_7DAY, _LAST_VALID_LOGS, _HERD_ITEMS_CACHE
        _AWS_CACHE.clear()
        _LAST_VALID_DASHBOARD.clear()
        _LAST_VALID_7DAY.clear()
        _LAST_VALID_LOGS.clear()
        _HERD_ITEMS_CACHE = {"expires_at": 0.0, "data": []}
        if os.path.exists(SNAPSHOT_FILE):
            try:
                os.remove(SNAPSHOT_FILE)
            except Exception:
                pass
        logger.info("Cleared all AWS telemetry caches and removed snapshot file.")

    @classmethod
    def load_all_tag_metadata(cls):
        """Preload all tags from DB in ONE single query to avoid thread contention."""
        global _METADATA_CACHE, _TAGS_LOADED_AT
        now = time.time()
        if (now - _TAGS_LOADED_AT) < 60.0:
            return

        _TAGS_LOADED_AT = now
        try:
            from app.database import SessionLocal
            from app.models.tag_registry import TagRegistry
            with SessionLocal() as db:
                tags = db.query(TagRegistry).all()
                for tag in tags:
                    dev_str = str(tag.device_id).strip()
                    clean_id = dev_str.lower().replace("aws-", "")
                    weight_val = f"{tag.weight} kg" if tag.weight and not str(tag.weight).endswith("kg") else (tag.weight or "480 kg")
                    tag_no = f"AWS {clean_id}"
                    meta = {
                        "name": tag.name or f"AWS {clean_id}",
                        "breed": tag.breed or None,
                        "location": tag.location or "Paddock AWS",
                        "weight": weight_val,
                        "notes": tag.notes or "Registered in Tag Registry",
                        "tagNumber": tag_no
                    }
                    _METADATA_CACHE[clean_id] = {"expires_at": now + 120, "data": meta}
                    _METADATA_CACHE[dev_str] = {"expires_at": now + 120, "data": meta}
        except Exception as e:
            logger.warning(f"Error preloading TagRegistry: {e}")

        # Ensure all configured AWS devices have default cache entries
        for dev_id in settings.AWS_ENABLED_DEVICE_IDS:
            dev_str = str(dev_id).strip()
            clean_id = dev_str.lower().replace("aws-", "")
            if clean_id not in _METADATA_CACHE:
                meta = {
                    "name": f"AWS {clean_id}",
                    "breed": None,
                    "location": "Paddock AWS",
                    "weight": "480 kg",
                    "notes": "AWS Collar Node",
                    "tagNumber": f"AWS {clean_id}"
                }
                _METADATA_CACHE[clean_id] = {"expires_at": now + 120, "data": meta}
                _METADATA_CACHE[dev_str] = {"expires_at": now + 120, "data": meta}

    @classmethod
    def get_device_metadata(cls, device_id: str) -> dict:
        """
        Dynamically fetch cow metadata from TagRegistry in DB.
        Falls back to default config only if no TagRegistry record exists.
        """
        dev_str = str(device_id).strip()
        clean_id = dev_str.lower().replace("aws-", "")
        now = time.time()

        cached = _METADATA_CACHE.get(clean_id) or _METADATA_CACHE.get(dev_str)
        if not cached or cached.get("expires_at", 0) <= now:
            cls.load_all_tag_metadata()
            cached = _METADATA_CACHE.get(clean_id) or _METADATA_CACHE.get(dev_str)

        if cached and cached.get("data"):
            return cached["data"]

        meta = {
            "name": f"AWS {clean_id}",
            "breed": None,
            "location": "Paddock AWS",
            "weight": "480 kg",
            "notes": "AWS Collar Node",
            "tagNumber": f"AWS {clean_id}"
        }
        _METADATA_CACHE[clean_id] = {"expires_at": now + 120, "data": meta}
        _METADATA_CACHE[dev_str] = {"expires_at": now + 120, "data": meta}
        return meta

    @classmethod
    def get_live_dashboard(cls, device_id: str, target_date: str = None) -> dict:
        """
        Builds the Live Diagnostics dashboard payload for an AWS device.
        Matches exact schema of get_cow_live_dashboard in cows.py.
        Targets specific date for 24 hours (startdate=target&enddate=target).
        If today has NO packets, today's activity totals are strictly 0.0 and node is marked stale/offline.
        """
        now = datetime.now(timezone.utc)
        today_date_str = now.strftime("%d-%m-%Y")
        is_querying_today = (target_date is None or target_date == today_date_str)
        target = target_date or today_date_str

        cache_key = f"live_{device_id}_{target}"
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached.get("expires_at", 0) > time.time():
            return cached["data"]

        packets = cls.get_processed_packets(device_id, start_date=target, end_date=target)
        dev_meta = cls.get_device_metadata(device_id)
        dev_key = str(device_id).strip()

        # Filter packets strictly belonging to target date
        target_date_obj = datetime.strptime(target, "%d-%m-%Y").date()
        target_packets = [p for p in packets if p["timestamp"].date() == target_date_obj]
        if not target_packets and not is_querying_today:
            target_packets = packets

        # If device has no packets for this target date (e.g. today has no data)
        if not target_packets:
            last_known = _LAST_KNOWN_TELEMETRY.get(dev_key)
            last_telem = last_known["telemetry"] if last_known else {"x": 0, "y": 0, "z": 0, "magnitude": 0, "timestamp": now.isoformat()}
            last_accel = last_known["accelBuffer"] if last_known else {"labels": [f"{(i*0.1):.1f}s" for i in range(80)], "x": [0]*80, "y": [0]*80, "z": [0]*80, "mag": [0]*80}
            if packets:
                p_last = packets[-1]
                x_b = p_last["x_buf"]
                y_b = p_last["y_buf"]
                z_b = p_last["z_buf"]
                m_b = [round(math.sqrt(x_b[i]**2 + y_b[i]**2 + z_b[i]**2), 3) for i in range(len(x_b))]
                last_telem = {"x": x_b[-1] if x_b else 0, "y": y_b[-1] if y_b else 0, "z": z_b[-1] if z_b else 0, "magnitude": m_b[-1] if m_b else 0, "timestamp": p_last["timestamp"].isoformat()}
                last_accel = {"labels": [f"{(i*0.1):.1f}s" for i in range(len(x_b))], "x": x_b, "y": y_b, "z": z_b, "mag": m_b}

            empty_res = {
                "cowId": f"aws-{device_id}",
                "device_id": str(device_id),
                "source": "aws_api",
                "cowName": dev_meta["name"],
                "tagNumber": dev_meta["tagNumber"],
                "breed": dev_meta["breed"],
                "location": dev_meta["location"],
                "weight": dev_meta["weight"],
                "notes": dev_meta["notes"],
                "isStale": True,
                "currentActivity": {
                    "code": None,
                    "name": "No Recent Data",
                    "color": "#64748b",
                    "icon": "fa-pause"
                },
                "healthStatus": {
                    "monitoredHoursToday": 0.0,
                    "ruminationHoursToday": 0.0,
                    "lyingHoursToday": 0.0,
                    "feedingHoursToday": 0.0,
                    "movingHoursToday": 0.0,
                    "ruminationScore": 0,
                    "estrusProbabilityPercent": 0,
                    "isHeatDetected": False,
                    "healthRecommendation": "WARNING: No sensor data received today. Check collar node battery and uplink connectivity.",
                    "health_risk_decision": "NO_DATA"
                },
                "liveTelemetry": last_telem,
                "accelBuffer": last_accel,
                "ml_inference": {
                    "ml_engine_status": "OFFLINE",
                    "activity": {"code": None, "confidence": 0.0},
                    "heat_detection": {"in_heat": False, "heat_probability": 0.0, "alert_level": "NORMAL"},
                    "anomaly_detection": {"is_anomaly": False, "score": 0.0},
                    "health_risk_decision": "NO_DATA"
                }
            }
            _LAST_VALID_DASHBOARD[dev_key] = empty_res
            _save_snapshot()
            _AWS_CACHE[cache_key] = {"expires_at": time.time() + 60.0, "data": empty_res}
            return empty_res

        # Latest packet of target date is the last one in the sorted list
        latest = target_packets[-1]
        latest_ts = latest["timestamp"]
        
        # Check staleness (if last data is older than 24h)
        is_stale = (now - latest_ts).total_seconds() > (24 * 3600)

        total_pkts = len(target_packets)
        monitored_hours = round((total_pkts * AWS_PACKET_INTERVAL_SECONDS) / 3600.0, 2)

        counts = {"RUS": 0, "REL": 0, "FEP": 0, "MOV": 0, "RES": 0, "HEAT": 0}
        for p in target_packets:
            inf = p["ml_inference"]
            code = inf["activity"]["code"]
            if code in ["RUS"]:
                counts["RUS"] += 1
            elif code in ["REL"]:
                counts["REL"] += 1
            elif code in ["FEP", "FED", "GRZ"]:
                counts["FEP"] += 1
            elif code in ["MOV"]:
                counts["MOV"] += 1
            elif code in ["RES"]:
                counts["RES"] += 1

            if inf["heat_detection"]["in_heat"]:
                counts["HEAT"] += 1

        rum_hrs = round((counts["RUS"] * AWS_PACKET_INTERVAL_SECONDS) / 3600.0, 2)
        lying_hrs = round((counts["REL"] * AWS_PACKET_INTERVAL_SECONDS) / 3600.0, 2)
        feed_hrs = round((counts["FEP"] * AWS_PACKET_INTERVAL_SECONDS) / 3600.0, 2)
        move_hrs = round((counts["MOV"] * AWS_PACKET_INTERVAL_SECONDS) / 3600.0, 2)

        latest_ml = latest["ml_inference"]
        act_code = latest_ml["activity"]["code"]
        act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP["RES"])

        is_heat = latest_ml["heat_detection"]["in_heat"] or (counts["HEAT"] > 0)
        heat_prob_pct = int(latest_ml["heat_detection"]["heat_probability"] * 100)
        health_risk = latest_ml.get("health_risk_decision", "HEALTHY")

        if is_heat and health_risk == "HEALTHY":
            health_risk = "HIGH_RISK"

        # Generate clinical recommendation
        if health_risk == "HIGH_RISK":
            if is_heat:
                recommendation = "CRITICAL: Cow is showing signs of being in heat (estrus cycle). Action needed: Prepare for artificial insemination (breeding) in the next 12 hours."
            elif latest_ml.get("anomaly_detection", {}).get("is_anomaly"):
                recommendation = "CRITICAL: Unusual movement patterns detected (anomaly). Action needed: Physically check the cow for injury or sickness."
            else:
                recommendation = "CRITICAL: Health risk detected by ML models. Action needed: Physically examine the animal immediately."
        elif health_risk == "MONITOR":
            recommendation = "MONITOR: Early behavioral deviations detected. Observe node closely over the next 6-12 hours."
        else:
            recommendation = "All health parameters within normal range based on real-time AWS telemetry analysis."

        x_buf = latest["x_buf"]
        y_buf = latest["y_buf"]
        z_buf = latest["z_buf"]
        mag_buf = [round(math.sqrt(x_buf[i]**2 + y_buf[i]**2 + z_buf[i]**2), 3) for i in range(len(x_buf))]
        labels = [f"{(i*0.1):.1f}s" for i in range(len(x_buf))]

        live_payload = {
            "cowId": f"aws-{device_id}",
            "device_id": str(device_id),
            "source": "aws_api",
            "cowName": dev_meta["name"],
            "tagNumber": dev_meta.get("tagNumber") or f"AWS {device_id}",
            "breed": dev_meta["breed"],
            "location": dev_meta["location"],
            "weight": dev_meta["weight"],
            "notes": dev_meta["notes"],
            "isStale": is_stale,
            "currentActivity": {
                "code": act_code,
                "name": act_info["name"],
                "color": act_info["color"],
                "icon": act_info["icon"]
            },
            "healthStatus": {
                "monitoredHoursToday": monitored_hours,
                "ruminationHoursToday": rum_hrs,
                "lyingHoursToday": lying_hrs,
                "feedingHoursToday": feed_hrs,
                "movingHoursToday": move_hrs,
                "ruminationScore": min(100, int((rum_hrs / 8.0) * 100)) if rum_hrs > 0 else 0,
                "estrusProbabilityPercent": heat_prob_pct,
                "isHeatDetected": is_heat,
                "healthRecommendation": recommendation,
                "health_risk_decision": health_risk
            },
            "liveTelemetry": {
                "x": x_buf[-1] if x_buf else 0,
                "y": y_buf[-1] if y_buf else 0,
                "z": z_buf[-1] if z_buf else 0,
                "magnitude": mag_buf[-1] if mag_buf else 0,
                "timestamp": latest_ts.isoformat()
            },
            "accelBuffer": {
                "labels": labels,
                "x": x_buf,
                "y": y_buf,
                "z": z_buf,
                "mag": mag_buf
            },
            "ml_inference": latest_ml
        }
        _LAST_VALID_DASHBOARD[str(device_id).strip()] = live_payload
        _LAST_KNOWN_TELEMETRY[str(device_id).strip()] = {
            "telemetry": live_payload["liveTelemetry"],
            "accelBuffer": live_payload["accelBuffer"],
            "timestamp": latest_ts.isoformat()
        }
        _save_snapshot()
        _AWS_CACHE[cache_key] = {"expires_at": time.time() + 60.0, "data": live_payload}
        return live_payload

    @classmethod
    def _update_daily_summary_from_packets(cls, dev_id: str, d: date, pkts: list):
        """Update _AWS_DAILY_SUMMARIES for a specific device and date."""
        dev_key = str(dev_id).strip()
        d_str = d.strftime("%Y-%m-%d")
        if dev_key not in _AWS_DAILY_SUMMARIES:
            _AWS_DAILY_SUMMARIES[dev_key] = {}

        if not pkts:
            _AWS_DAILY_SUMMARIES[dev_key][d_str] = {
                "monitored_hours": 0.0,
                "rum_hours": 0.0,
                "lying_hours": 0.0,
                "feed_hours": 0.0,
                "move_hours": 0.0,
                "heat_count": 0,
                "total_packets": 0,
                "health_score": 0,
                "estrus_index": 0
            }
            return

        tot = len(pkts)
        mon_hrs = round((tot * AWS_PACKET_INTERVAL_SECONDS) / 3600.0, 2)
        c_rus = sum(1 for p in pkts if p["ml_inference"]["activity"]["code"] == "RUS")
        c_rel = sum(1 for p in pkts if p["ml_inference"]["activity"]["code"] == "REL")
        c_fep = sum(1 for p in pkts if p["ml_inference"]["activity"]["code"] in ["FEP", "FED", "GRZ"])
        c_mov = sum(1 for p in pkts if p["ml_inference"]["activity"]["code"] == "MOV")
        c_heat = sum(1 for p in pkts if p["ml_inference"]["heat_detection"]["in_heat"])
        r_hrs = round((c_rus * AWS_PACKET_INTERVAL_SECONDS) / 3600.0, 2)
        l_hrs = round((c_rel * AWS_PACKET_INTERVAL_SECONDS) / 3600.0, 2)
        f_hrs = round((c_fep * AWS_PACKET_INTERVAL_SECONDS) / 3600.0, 2)
        m_hrs = round((c_mov * AWS_PACKET_INTERVAL_SECONDS) / 3600.0, 2)
        h_score = min(100, int((r_hrs / 8.0) * 100)) if r_hrs > 0 else (50 if (l_hrs > 0 or f_hrs > 0) else 0)
        e_idx = int((c_heat / tot) * 100) if tot > 0 else 0

        _AWS_DAILY_SUMMARIES[dev_key][d_str] = {
            "monitored_hours": mon_hrs,
            "rum_hours": r_hrs,
            "lying_hours": l_hrs,
            "feed_hours": f_hrs,
            "move_hours": m_hrs,
            "heat_count": c_heat,
            "total_packets": tot,
            "health_score": h_score,
            "estrus_index": min(100, e_idx)
        }

    @classmethod
    def get_7day_activity(cls, device_id: str) -> dict:
        """
        Builds the 7-day behavior distribution for an AWS device.
        Dynamically computes the rolling 7-day date window ending TODAY.
        Past days are cached permanently / in snapshot for instant sub-second responses.
        Only today's date is queried from AWS (or refreshed if expired).
        """
        dev_key = str(device_id).strip()
        now = datetime.now(timezone.utc)
        today = now.date()
        today_str = today.strftime("%Y-%m-%d")
        today_aws_fmt = today.strftime("%d-%m-%Y")

        date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]
        day_labels = [d.strftime("%a") for d in date_range]
        date_labels = [d.strftime("%Y-%m-%d") for d in date_range]

        cache_key = f"7day_{dev_key}_{today_str}"
        now_ts = time.time()
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached.get("expires_at", 0) > now_ts:
            return cached["data"]

        # Collect missing days:
        # Past days (d < today): fetch once and cache in _AWS_DAILY_SUMMARIES
        # Today (d == today): query AWS if raw cache expired
        missing_days = []
        for d in date_range:
            d_str = d.strftime("%Y-%m-%d")
            if d == today:
                today_cache_key = f"raw_{dev_key}_{today_aws_fmt}_{today_aws_fmt}"
                c_today = _AWS_CACHE.get(today_cache_key)
                if not c_today or c_today["expires_at"] <= now_ts:
                    missing_days.append(d)
            else:
                if dev_key not in _AWS_DAILY_SUMMARIES or d_str not in _AWS_DAILY_SUMMARIES[dev_key]:
                    missing_days.append(d)

        if missing_days:
            def fetch_single_day(d: date):
                day_fmt = d.strftime("%d-%m-%Y")
                return d, cls.get_processed_packets(dev_key, start_date=day_fmt, end_date=day_fmt)

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(missing_days))) as executor:
                future_map = {executor.submit(fetch_single_day, d): d for d in missing_days}
                for fut in concurrent.futures.as_completed(future_map):
                    try:
                        d, pkts = fut.result()
                        cls._update_daily_summary_from_packets(dev_key, d, pkts)
                    except Exception as e:
                        d = future_map[fut]
                        logger.warning(f"Error fetching AWS day {d} for {dev_key}: {e}")
                        cls._update_daily_summary_from_packets(dev_key, d, [])

        rum_list, lying_list, feed_list, act_list = [], [], [], []
        monitored_list, health_score_list, estrus_index_list = [], [], []

        for d in date_range:
            d_str = d.strftime("%Y-%m-%d")
            s = _AWS_DAILY_SUMMARIES.get(dev_key, {}).get(d_str, {
                "monitored_hours": 0.0, "rum_hours": 0.0, "lying_hours": 0.0,
                "feed_hours": 0.0, "move_hours": 0.0, "health_score": 0, "estrus_index": 0
            })
            rum_list.append(s["rum_hours"])
            lying_list.append(s["lying_hours"])
            feed_list.append(s["feed_hours"])
            act_list.append(s["move_hours"])
            monitored_list.append(s["monitored_hours"])
            health_score_list.append(s["health_score"])
            estrus_index_list.append(s["estrus_index"])

        weekly_avg = {
            "RUS": round(sum(rum_list) / 7.0, 4),
            "REL": round(sum(lying_list) / 7.0, 4),
            "FEP": round(sum(feed_list) / 7.0, 4),
            "MOV": round(sum(act_list) / 7.0, 4),
            "RES": 0.0,
            "DRN": 0.0
        }

        result = {
            "cowId": f"aws-{dev_key}",
            "device_id": str(dev_key),
            "source": "aws_api",
            "days": day_labels,
            "dates": date_labels,
            "ruminationHours": rum_list,
            "lyingRestHours": lying_list,
            "feedingHours": feed_list,
            "activeHours": act_list,
            "monitoredHours": monitored_list,
            "healthScores": health_score_list,
            "estrusIndices": estrus_index_list,
            "estrusAlerts": [],
            "weeklyAverageHours": weekly_avg
        }

        # Cache 7-day result for 60 seconds (today refreshes every minute)
        _AWS_CACHE[cache_key] = {"expires_at": time.time() + 60.0, "data": result}
        _save_snapshot()
        return result

    @classmethod
    def get_activity_logs(cls, device_id: str, page: int = 1, limit: int = 20) -> dict:
        """
        Builds chronological activity transition logs for an AWS device across the 7-day window.
        Uses cached processed packets for past days, queries/caches today.
        Breaks sessions on activity change, packet gaps (>120s), and date changes.
        """
        dev_key = str(device_id).strip()
        now = datetime.now(timezone.utc)
        today = now.date()
        date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]

        cache_key = f"actlogs_{dev_key}_{today.strftime('%Y-%m-%d')}"
        now_ts = time.time()
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached.get("expires_at", 0) > now_ts:
            all_grouped = cached["data"]
            start_idx = (page - 1) * limit
            return {
                "success": True,
                "logs": all_grouped[start_idx : start_idx + limit],
                "page": page,
                "limit": limit,
                "totalLogs": len(all_grouped),
                "source": "aws_api"
            }

        # Collect packets across the 7 days
        all_packets = []
        for d in date_range:
            d_fmt = d.strftime("%d-%m-%Y")
            pkts = cls.get_processed_packets(dev_key, start_date=d_fmt, end_date=d_fmt)
            if pkts:
                all_packets.extend(pkts)

        all_packets.sort(key=lambda p: p["timestamp"])

        grouped_logs = []
        current_group = None
        last_ts = None

        for idx, p in enumerate(all_packets):
            inf = p["ml_inference"]
            act_code = inf["activity"]["code"]
            conf = int(inf["activity"]["confidence"] * 100)
            ts = p["timestamp"]
            is_gap = last_ts and (ts - last_ts).total_seconds() > 120
            is_day_change = last_ts and (ts.date() != last_ts.date())

            if current_group and current_group["activityCode"] == act_code and not is_gap and not is_day_change:
                current_group["endTime"] = ts.isoformat()
                current_group["packetCount"] += 1
                current_group["endPacketId"] = f"AWS-P{idx+1}"
                current_group["confidenceSum"] += conf
            else:
                if current_group:
                    grouped_logs.append(current_group)
                act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP["RES"])
                current_group = {
                    "logId": f"aws-{dev_key}-{idx+1}",
                    "startTime": ts.isoformat(),
                    "endTime": ts.isoformat(),
                    "packetCount": 1,
                    "activityCode": act_code,
                    "activityName": act_info["name"],
                    "color": act_info["color"],
                    "category": act_info["category"],
                    "confidenceSum": conf,
                    "startPacketId": f"AWS-P{idx+1}",
                    "endPacketId": f"AWS-P{idx+1}"
                }
            last_ts = ts

        if current_group:
            grouped_logs.append(current_group)

        for g in grouped_logs:
            pkt_count = g.get("packetCount", 1)
            duration_secs = max(60, pkt_count * 60)
            if duration_secs < 60:
                g["durationDisplay"] = f"{duration_secs} secs"
            elif duration_secs < 3600:
                mins = duration_secs // 60
                g["durationDisplay"] = f"{mins} mins" if mins > 1 else "1 min"
            else:
                hrs = duration_secs // 3600
                mins = round((duration_secs % 3600) / 60)
                if mins == 60:
                    hrs += 1
                    mins = 0
                g["durationDisplay"] = f"{hrs}h {mins}m" if mins > 0 else f"{hrs}h"
            g["durationStr"] = g["durationDisplay"]
            g["durationMinutes"] = max(1, round(duration_secs / 60))
            g["confidencePercent"] = round(g["confidenceSum"] / pkt_count)
            del g["packetCount"]
            del g["confidenceSum"]

        # Merge with existing historical logs so temporary AWS timeouts never discard past days
        existing = _LAST_VALID_LOGS.get(dev_key, [])
        if isinstance(existing, dict):
            existing = existing.get("logs", [])
        if existing:
            new_dates = set(l["startTime"][:10] for l in grouped_logs if l.get("startTime"))
            for old_log in existing:
                old_date = old_log.get("startTime", "")[:10]
                if old_date and old_date != today.strftime("%Y-%m-%d") and old_date not in new_dates:
                    grouped_logs.append(old_log)

        grouped_logs.sort(key=lambda x: x.get("startTime", ""), reverse=True)
        if grouped_logs:
            _LAST_VALID_LOGS[dev_key] = grouped_logs
            _save_snapshot()
        _AWS_CACHE[cache_key] = {"expires_at": time.time() + 60.0, "data": grouped_logs}

        start_idx = (page - 1) * limit
        return {
            "success": True,
            "logs": grouped_logs[start_idx : start_idx + limit],
            "page": page,
            "limit": limit,
            "totalLogs": len(grouped_logs),
            "source": "aws_api"
        }

    @classmethod
    def _build_device_overview(cls, dash: dict) -> dict:
        h = dash.get("healthStatus", {})
        act = dash.get("currentActivity", {})
        dev_id = str(dash.get("device_id", "")).strip()
        last_seen = dash.get("liveTelemetry", {}).get("timestamp")

        is_today = False
        if last_seen:
            try:
                dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                today_utc = datetime.now(timezone.utc).date()
                if dt.date() == today_utc:
                    is_today = True
            except Exception:
                pass

        is_stale = dash.get("isStale", False) or (not is_today) or (h.get("monitoredHoursToday", 0.0) == 0.0)
        return {
            "id": f"aws-{dev_id}",
            "device_id": dev_id,
            "source": "aws_api",
            "tagNumber": dash.get("tagNumber") or f"AWS {dev_id}",
            "name": dash.get("cowName") or f"AWS {dev_id}",
            "breed": dash.get("breed"),
            "location": dash.get("location") or "Paddock AWS",
            "weight": dash.get("weight") or "480 kg",
            "healthStatus": "NO_DATA" if is_stale else h.get("health_risk_decision", "NORMAL"),
            "health_risk_decision": "NO_DATA" if is_stale else h.get("health_risk_decision", "NORMAL"),
            "currentActivity": None if is_stale else (act.get("code") if act else None),
            "activityName": "No Recent Data" if is_stale else (act.get("name", "Standing Rest") if act else "Standing Rest"),
            "ruminationHoursToday": 0.0 if is_stale else h.get("ruminationHoursToday", 0.0),
            "lyingHoursToday": 0.0 if is_stale else h.get("lyingHoursToday", 0.0),
            "feedingHoursToday": 0.0 if is_stale else h.get("feedingHoursToday", 0.0),
            "movingHoursToday": 0.0 if is_stale else h.get("movingHoursToday", 0.0),
            "estrusProbability": 0 if is_stale else h.get("estrusProbabilityPercent", 0),
            "lastSeen": last_seen or datetime.now(timezone.utc).isoformat(),
            "isStale": is_stale,
            "monitoredHoursToday": 0.0 if is_stale else h.get("monitoredHoursToday", 0.0)
        }

    @classmethod
    def _fetch_single_herd_item(cls, dev_id: str) -> dict:
        dev_str = str(dev_id).strip()
        dash = cls.get_live_dashboard(dev_str)
        return cls._build_device_overview(dash)

    @classmethod
    def _build_fallback_herd_items(cls, device_ids: List[str] = None) -> List[dict]:
        """
        Builds instantaneous placeholder items from TagRegistry / metadata cache.
        Returns in 0ms so the HTTP request NEVER hangs.
        """
        if not device_ids:
            device_ids = settings.AWS_ENABLED_DEVICE_IDS

        items = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for dev_id in device_ids:
            dev_str = str(dev_id).strip()
            clean_id = dev_str.lower().replace("aws-", "")

            # If we have valid live telemetry snapshot for this node, use it directly!
            if clean_id in _LAST_VALID_DASHBOARD:
                items.append(cls._build_device_overview(_LAST_VALID_DASHBOARD[clean_id]))
                continue
            if dev_str in _LAST_VALID_DASHBOARD:
                items.append(cls._build_device_overview(_LAST_VALID_DASHBOARD[dev_str]))
                continue

            cached = _METADATA_CACHE.get(clean_id) or _METADATA_CACHE.get(dev_str)
            meta = cached["data"] if (cached and cached.get("data")) else {
                "name": f"AWS {clean_id}",
                "breed": None,
                "location": "Paddock AWS",
                "weight": "480 kg",
                "notes": "AWS Collar Node",
                "tagNumber": f"AWS {clean_id}"
            }
            items.append({
                "id": f"aws-{clean_id}",
                "device_id": clean_id,
                "source": "aws_api",
                "tagNumber": meta.get("tagNumber") or f"AWS {clean_id}",
                "name": meta.get("name") or f"AWS {clean_id}",
                "breed": meta.get("breed"),
                "location": meta.get("location") or "Paddock AWS",
                "weight": meta.get("weight") or "480 kg",
                "healthStatus": "NO_DATA",
                "health_risk_decision": "NO_DATA",
                "currentActivity": None,
                "activityName": "No Recent Data",
                "ruminationHoursToday": 0.0,
                "lyingHoursToday": 0.0,
                "feedingHoursToday": 0.0,
                "movingHoursToday": 0.0,
                "estrusProbability": 0,
                "lastSeen": now_iso,
                "isStale": True,
                "monitoredHoursToday": 0.0
            })
        return items

    @classmethod
    def _trigger_background_herd_refresh(cls, device_ids: List[str] = None):
        global _HERD_IS_REFRESHING
        with _REFRESH_THREAD_LOCK:
            if _HERD_IS_REFRESHING:
                return
            _HERD_IS_REFRESHING = True

        if not device_ids:
            device_ids = settings.AWS_ENABLED_DEVICE_IDS

        def worker():
            global _HERD_IS_REFRESHING, _HERD_ITEMS_CACHE
            try:
                cls.load_all_tag_metadata()
                items = []
                # Use max_workers=2 to prevent saturating Render's 0.1 vCPU
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_to_dev = {executor.submit(cls._fetch_single_herd_item, dev_id): dev_id for dev_id in device_ids}
                    for future in concurrent.futures.as_completed(future_to_dev):
                        try:
                            item = future.result()
                            if item:
                                items.append(item)
                        except Exception as e:
                            dev_id = future_to_dev[future]
                            logger.warning(f"Error fetching AWS overview item for dev {dev_id}: {e}")

                if items:
                    device_order = {str(d).strip(): idx for idx, d in enumerate(device_ids)}
                    items.sort(key=lambda x: device_order.get(x["device_id"], 999))
                    _HERD_ITEMS_CACHE = {
                        "expires_at": time.time() + CACHE_TTL_SECONDS,
                        "data": items
                    }
                    logger.info(f"Background herd refresh completed successfully with {len(items)} devices.")
            except Exception as e:
                logger.error(f"Error in background herd refresh: {e}")
            finally:
                with _REFRESH_THREAD_LOCK:
                    _HERD_IS_REFRESHING = False

        t = threading.Thread(target=worker, daemon=True, name="AwsHerdRefreshWorker")
        t.start()

    @classmethod
    def get_herd_overview_items(cls, device_ids: List[str] = None, force_refresh: bool = False) -> List[dict]:
        """
        Returns list of herd overview summary dicts for all configured AWS devices.
        STRICTLY NON-BLOCKING: Always returns immediately (<5ms) using Stale-While-Revalidate.
        Background daemon thread refreshes live telemetry.
        """
        global _HERD_ITEMS_CACHE
        now = time.time()

        if not device_ids:
            device_ids = settings.AWS_ENABLED_DEVICE_IDS

        # If cache exists and is fresh, return immediately
        if not force_refresh and _HERD_ITEMS_CACHE.get("expires_at", 0) > now and _HERD_ITEMS_CACHE.get("data"):
            return _HERD_ITEMS_CACHE["data"]

        # If cache exists but is stale, trigger background refresh and return stale data immediately
        if _HERD_ITEMS_CACHE.get("data"):
            cls._trigger_background_herd_refresh(device_ids)
            return _HERD_ITEMS_CACHE["data"]

        # Cold start: populate instant fallback items, trigger background refresh, and return immediately
        fallback_items = cls._build_fallback_herd_items(device_ids)
        _HERD_ITEMS_CACHE = {
            "expires_at": now + 30,
            "data": fallback_items
        }
        cls._trigger_background_herd_refresh(device_ids)
        return fallback_items


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

# In-memory caches for high-speed API performance
_AWS_CACHE: Dict[str, Dict[str, Any]] = {}
_HERD_ITEMS_CACHE: Dict[str, Any] = {"expires_at": 0.0, "data": []}
_METADATA_CACHE: Dict[str, Dict[str, Any]] = {}
_ML_PREDICTION_CACHE: Dict[str, Any] = {}
_HERD_IS_REFRESHING = False
_REFRESH_THREAD_LOCK = threading.Lock()
_TAGS_LOADED_AT = 0.0
CACHE_TTL_SECONDS = 300


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

        cache_key = f"raw_{device_id}_{resolved_start}_{resolved_end}"
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"]

        url = f"{settings.AWS_COWNECK_API_URL}?deviceid={device_id}&startdate={resolved_start}&enddate={resolved_end}"

        # Use shorter read timeout for past days — they either have data or they don't.
        # requests(timeout=(connect_s, read_s)) enforces both connection AND read independently.
        today_str = now.strftime("%d-%m-%Y")
        is_today = (resolved_start == today_str)
        read_timeout = 12 if is_today else 7

        try:
            if _requests is not None:
                resp = _requests.get(
                    url,
                    headers={"User-Agent": "CowMonitoring-Backend/1.0"},
                    timeout=(3, read_timeout),  # (connect_timeout, read_timeout)
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
            # Cache empty/error for past days to avoid repeated slow timeouts
            if not is_today:
                _AWS_CACHE[cache_key] = {
                    "expires_at": time.time() + 86400,
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
        """Clears all caches for immediate dynamic UI updates."""
        global _AWS_CACHE, _HERD_ITEMS_CACHE, _METADATA_CACHE, _ML_PREDICTION_CACHE, _TAGS_LOADED_AT
        _AWS_CACHE.clear()
        _HERD_ITEMS_CACHE = {"expires_at": 0.0, "data": []}
        _METADATA_CACHE.clear()
        _ML_PREDICTION_CACHE.clear()
        _TAGS_LOADED_AT = 0.0
        logger.info("Cleared AWS service caches.")

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
                        "breed": tag.breed or "CowNeck Collar Cow",
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
                    "breed": "CowNeck Collar Cow",
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
            "breed": "CowNeck Collar Cow",
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
        """
        now = datetime.now(timezone.utc)
        target = target_date or now.strftime("%d-%m-%Y")

        cache_key = f"live_{device_id}_{target}"
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached.get("expires_at", 0) > time.time():
            return cached["data"]

        packets = cls.get_processed_packets(device_id, start_date=target, end_date=target)

        # Fallback to yesterday's 24h window if today has no packets and no explicit target was forced
        if not packets and not target_date:
            yesterday_str = (now - timedelta(days=1)).strftime("%d-%m-%Y")
            packets = cls.get_processed_packets(device_id, start_date=yesterday_str, end_date=yesterday_str)

        dev_meta = cls.get_device_metadata(device_id)

        if not packets:
            now = datetime.now(timezone.utc)
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
                    "name": "No AWS Data",
                    "color": "#64748b",
                    "icon": "fa-question"
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
                    "healthRecommendation": "No sensor packets returned by AWS CowNeck API for this device.",
                    "health_risk_decision": "NO_DATA"
                },
                "liveTelemetry": {"x": 0, "y": 0, "z": 0, "magnitude": 0, "timestamp": now.isoformat()},
                "accelBuffer": {"labels": [f"{(i*0.1):.1f}s" for i in range(80)], "x": [0]*80, "y": [0]*80, "z": [0]*80, "mag": [0]*80},
                "ml_inference": {
                    "ml_engine_status": "NO_DATA",
                    "activity": {"code": "RES", "confidence": 0.0},
                    "heat_detection": {"in_heat": False, "heat_probability": 0.0, "alert_level": "NORMAL"},
                    "anomaly_detection": {"is_anomaly": False, "score": 0.0},
                    "health_risk_decision": "NO_DATA"
                }
            }
            _AWS_CACHE[cache_key] = {"expires_at": time.time() + 60.0, "data": empty_res}
            return empty_res

        # Latest packet is the last one in the sorted list
        latest = packets[-1]
        latest_ts = latest["timestamp"]
        
        # Check staleness (if last data is older than 24h)
        now = datetime.now(timezone.utc)
        is_stale = (now - latest_ts).total_seconds() > (24 * 3600)

        # Calculate today's activities from packets
        # In case test date is 2026-09-22, we consider the date of the latest packet as the active day
        active_date = latest_ts.date()
        today_packets = [p for p in packets if p["timestamp"].date() == active_date]
        if not today_packets:
            today_packets = packets

        total_pkts = len(today_packets)
        monitored_hours = round((total_pkts * 8.0) / 3600.0, 1)

        counts = {"RUS": 0, "REL": 0, "FEP": 0, "MOV": 0, "RES": 0, "HEAT": 0}
        for p in today_packets:
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

        rum_hrs = round((counts["RUS"] * 8.0) / 3600.0, 1)
        lying_hrs = round((counts["REL"] * 8.0) / 3600.0, 1)
        feed_hrs = round((counts["FEP"] * 8.0) / 3600.0, 1)
        move_hrs = round((counts["MOV"] * 8.0) / 3600.0, 1)

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
        _AWS_CACHE[cache_key] = {"expires_at": time.time() + 30.0, "data": live_payload}
        return live_payload

    @classmethod
    def get_7day_activity(cls, device_id: str) -> dict:
        """
        Builds the 7-day behavior distribution for an AWS device.
        Uses stale-while-revalidate: returns instantly from cache, refreshes in background.
        First call returns skeleton immediately and triggers background computation.
        Cache TTL: 30min (data doesn't change frequently within a day).
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cache_key = f"7day_{device_id}"
        cached = _AWS_CACHE.get(cache_key)
        now_ts = time.time()

        # Always build date range for skeleton response
        today = datetime.now(timezone.utc).date()
        date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]
        day_labels = [d.strftime("%a") for d in date_range]
        date_labels = [d.strftime("%Y-%m-%d") for d in date_range]

        def _build_result(pkts_by_date: dict) -> dict:
            """Build the full 7-day result from per-day packets dict."""
            rum_list, lying_list, feed_list, act_list = [], [], [], []
            monitored_list, health_score_list, estrus_index_list = [], [], []

            for d in date_range:
                day_pkts = pkts_by_date.get(d, [])
                if day_pkts:
                    tot = len(day_pkts)
                    mon_hrs = round((tot * 8.0) / 3600.0, 1)
                    c_rus = sum(1 for p in day_pkts if p["ml_inference"]["activity"]["code"] == "RUS")
                    c_rel = sum(1 for p in day_pkts if p["ml_inference"]["activity"]["code"] == "REL")
                    c_fep = sum(1 for p in day_pkts if p["ml_inference"]["activity"]["code"] in ["FEP", "FED", "GRZ"])
                    c_mov = sum(1 for p in day_pkts if p["ml_inference"]["activity"]["code"] == "MOV")
                    c_heat = sum(1 for p in day_pkts if p["ml_inference"]["heat_detection"]["in_heat"])
                    r_hrs = round((c_rus * 8.0) / 3600.0, 1)
                    l_hrs = round((c_rel * 8.0) / 3600.0, 1)
                    f_hrs = round((c_fep * 8.0) / 3600.0, 1)
                    m_hrs = round((c_mov * 8.0) / 3600.0, 1)
                    h_score = min(100, int((r_hrs / 8.0) * 100)) if r_hrs > 0 else (50 if (l_hrs > 0 or f_hrs > 0) else 0)
                    e_idx = int((c_heat / tot) * 100) if tot > 0 else 0
                    rum_list.append(r_hrs); lying_list.append(l_hrs)
                    feed_list.append(f_hrs); act_list.append(m_hrs)
                    monitored_list.append(mon_hrs)
                    health_score_list.append(h_score)
                    estrus_index_list.append(min(100, e_idx))
                else:
                    rum_list.append(0.0); lying_list.append(0.0)
                    feed_list.append(0.0); act_list.append(0.0)
                    monitored_list.append(0.0)
                    health_score_list.append(0); estrus_index_list.append(0)

            days_with_data = sum(1 for m in monitored_list if m > 0)
            tot_days = max(1, days_with_data)
            return {
                "cowId": f"aws-{device_id}", "device_id": str(device_id), "source": "aws_api",
                "days": day_labels, "dates": date_labels,
                "ruminationHours": rum_list, "lyingRestHours": lying_list,
                "feedingHours": feed_list, "activeHours": act_list,
                "monitoredHours": monitored_list, "healthScores": health_score_list,
                "estrusIndices": estrus_index_list, "estrusAlerts": [],
                "weeklyAverageHours": {
                    "RUS": round(sum(rum_list) / tot_days, 2),
                    "REL": round(sum(lying_list) / tot_days, 2),
                    "FEP": round(sum(feed_list) / tot_days, 2),
                    "MOV": round(sum(act_list) / tot_days, 2),
                    "RES": 0.0, "DRN": 0.0
                }
            }

        def _refresh_in_background():
            """Background thread: fetch all 7 days and update cache."""
            try:
                def fetch_day(d: date) -> tuple:
                    day_str = d.strftime("%d-%m-%Y")
                    pkts = cls.get_processed_packets(device_id, start_date=day_str, end_date=day_str)
                    return d, pkts

                pkts_by_date: dict = {}
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {executor.submit(fetch_day, d): d for d in date_range}
                    for future in as_completed(futures):
                        try:
                            day, pkts = future.result()
                            pkts_by_date[day] = pkts
                        except Exception as e:
                            d = futures[future]
                            logger.warning(f"7day bg fetch failed for {d}: {e}")
                            pkts_by_date[d] = []

                result = _build_result(pkts_by_date)
                _AWS_CACHE[cache_key] = {
                    "expires_at": now_ts + 1800,  # 30min cache
                    "data": result
                }
                logger.info(f"7-day activity cache updated for device {device_id}")
            except Exception as e:
                logger.error(f"7-day background refresh failed for {device_id}: {e}")

        # Cache HIT (fresh): return instantly
        if cached and cached["expires_at"] > now_ts:
            return cached["data"]

        # Cache HIT (stale): return stale data immediately + trigger background refresh
        if cached and cached.get("data"):
            import threading
            t = threading.Thread(target=_refresh_in_background, daemon=True, name=f"7DayRefresh-{device_id}")
            t.start()
            return cached["data"]  # Return stale instantly — UI will refetch later

        # Cache MISS (first ever call): trigger background refresh and return empty skeleton
        import threading
        t = threading.Thread(target=_refresh_in_background, daemon=True, name=f"7DayRefresh-{device_id}")
        t.start()

        # Return empty skeleton immediately — frontend will show loading state
        # and poll again once cache is populated
        return _build_result({})

    @classmethod
    def get_activity_logs(cls, device_id: str, page: int = 1, limit: int = 20) -> dict:
        """
        Builds chronological activity transition logs for an AWS device.
        Uses stale-while-revalidate: returns instantly from cache, refreshes in background.
        Cache TTL: 30min. First call returns empty while background fetches all 7 days.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cache_key = f"actlogs_{device_id}"
        cached = _AWS_CACHE.get(cache_key)
        now_ts = time.time()

        def _build_logs(all_packets: list) -> dict:
            """Build grouped activity logs from sorted packets list."""
            if not all_packets:
                return {"success": True, "logs": [], "page": page, "limit": limit,
                        "totalLogs": 0, "source": "aws_api"}

            grouped_logs = []
            current_group = None
            for idx, p in enumerate(all_packets):
                inf = p["ml_inference"]
                act_code = inf["activity"]["code"]
                conf = int(inf["activity"]["confidence"] * 100)
                ts = p["timestamp"]
                if current_group and current_group["activityCode"] == act_code:
                    current_group["endTime"] = ts.isoformat()
                    current_group["packetCount"] += 1
                    current_group["endPacketId"] = f"AWS-P{idx+1}"
                    current_group["confidenceSum"] += conf
                else:
                    if current_group:
                        grouped_logs.append(current_group)
                    act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP["RES"])
                    current_group = {
                        "logId": f"aws-{device_id}-{idx+1}",
                        "startTime": ts.isoformat(), "endTime": ts.isoformat(),
                        "packetCount": 1, "activityCode": act_code,
                        "activityName": act_info["name"], "color": act_info["color"],
                        "category": act_info["category"], "confidenceSum": conf,
                        "startPacketId": f"AWS-P{idx+1}", "endPacketId": f"AWS-P{idx+1}"
                    }
            if current_group:
                grouped_logs.append(current_group)

            for g in grouped_logs:
                start_ts = datetime.fromisoformat(g["startTime"])
                end_ts = datetime.fromisoformat(g["endTime"])
                duration_secs = max(8, int((end_ts - start_ts).total_seconds()) + 8)
                if duration_secs < 60:
                    g["durationDisplay"] = f"{duration_secs} secs"
                elif duration_secs < 3600:
                    g["durationDisplay"] = f"{round(duration_secs / 60)} mins"
                else:
                    hrs = duration_secs // 3600
                    mins = (duration_secs % 3600) // 60
                    g["durationDisplay"] = f"{hrs}h {mins}m" if mins > 0 else f"{hrs}h"
                g["durationMinutes"] = max(1, round(duration_secs / 60))
                g["confidencePercent"] = round(g["confidenceSum"] / g["packetCount"])
                del g["packetCount"]
                del g["confidenceSum"]

            grouped_logs.reverse()  # Newest first
            start_idx = (page - 1) * limit
            return {
                "success": True, "logs": grouped_logs[start_idx: start_idx + limit],
                "page": page, "limit": limit,
                "totalLogs": len(grouped_logs), "source": "aws_api"
            }

        def _refresh_in_background():
            """Background: fetch all 7 days and update logs cache."""
            try:
                today = datetime.now(timezone.utc).date()
                date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]

                def fetch_day(d: date) -> tuple:
                    day_str = d.strftime("%d-%m-%Y")
                    pkts = cls.get_processed_packets(device_id, start_date=day_str, end_date=day_str)
                    return d, pkts

                day_results: dict = {}
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {executor.submit(fetch_day, d): d for d in date_range}
                    for future in as_completed(futures):
                        try:
                            d, pkts = future.result()
                            day_results[d] = pkts
                        except Exception as e:
                            d = futures[future]
                            logger.warning(f"actlogs bg fetch failed for {d}: {e}")
                            day_results[d] = []

                all_packets = []
                for d in date_range:
                    all_packets.extend(day_results.get(d, []))
                all_packets.sort(key=lambda p: p["timestamp"])

                result = _build_logs(all_packets)
                _AWS_CACHE[cache_key] = {
                    "expires_at": now_ts + 1800,
                    "data": result
                }
                logger.info(f"Activity logs cache updated for device {device_id}: {result.get('totalLogs', 0)} log groups")
            except Exception as e:
                logger.error(f"Activity logs background refresh failed for {device_id}: {e}")

        # Cache HIT (fresh): return instantly
        if cached and cached["expires_at"] > now_ts:
            return cached["data"]

        # Cache HIT (stale): return immediately + trigger background refresh
        if cached and cached.get("data"):
            import threading
            t = threading.Thread(target=_refresh_in_background, daemon=True, name=f"LogsRefresh-{device_id}")
            t.start()
            return cached["data"]

        # Cache MISS: start background fetch, return empty immediately
        import threading
        t = threading.Thread(target=_refresh_in_background, daemon=True, name=f"LogsRefresh-{device_id}")
        t.start()
        return {"success": True, "logs": [], "page": page, "limit": limit,
                "totalLogs": 0, "source": "aws_api"}

    @classmethod
    def _fetch_single_herd_item(cls, dev_id: str) -> dict:
        dev_str = str(dev_id).strip()
        dash = cls.get_live_dashboard(dev_str)
        h = dash["healthStatus"]
        act = dash["currentActivity"]
        return {
            "id": f"aws-{dev_str}",
            "device_id": dev_str,
            "source": "aws_api",
            "tagNumber": dash.get("tagNumber") or f"AWS {dev_str}",
            "name": dash["cowName"],
            "breed": dash["breed"],
            "location": dash["location"],
            "weight": dash["weight"],
            "healthStatus": h["health_risk_decision"],
            "health_risk_decision": h["health_risk_decision"],
            "currentActivity": act["code"],
            "activityName": act["name"],
            "ruminationHoursToday": h["ruminationHoursToday"],
            "lyingHoursToday": h["lyingHoursToday"],
            "feedingHoursToday": h["feedingHoursToday"],
            "movingHoursToday": h["movingHoursToday"],
            "estrusProbability": h["estrusProbabilityPercent"],
            "lastSeen": dash["liveTelemetry"]["timestamp"],
            "isStale": dash["isStale"],
            "monitoredHoursToday": h["monitoredHoursToday"]
        }

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
            cached = _METADATA_CACHE.get(clean_id) or _METADATA_CACHE.get(dev_str)
            meta = cached["data"] if (cached and cached.get("data")) else {
                "name": f"AWS {clean_id}",
                "breed": "CowNeck Collar Cow",
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
                "location": meta.get("location"),
                "weight": meta.get("weight"),
                "healthStatus": "HEALTHY",
                "health_risk_decision": "HEALTHY",
                "currentActivity": "RES",
                "activityName": "Standing Rest",
                "ruminationHoursToday": 0.0,
                "lyingHoursToday": 0.0,
                "feedingHoursToday": 0.0,
                "movingHoursToday": 0.0,
                "estrusProbability": 0,
                "lastSeen": now_iso,
                "isStale": False,
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


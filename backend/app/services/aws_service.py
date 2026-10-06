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

# Standard Indian Standard Time (UTC+5:30) for AWS CowNeck collars and farm operations
IST = timezone(timedelta(hours=5, minutes=30))

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
_DISCOVERED_AWS_DEVICES: set = set()

_SNAPSHOT_LOCK = threading.Lock()

def _save_snapshot():
    with _SNAPSHOT_LOCK:
        tmp_file = None
        try:
            with _GLOBAL_LOCK:
                data = {
                    "dashboard": dict(_LAST_VALID_DASHBOARD),
                    "seven_day": dict(_LAST_VALID_7DAY),
                    "daily_summaries": {k: dict(v) for k, v in _AWS_DAILY_SUMMARIES.items()},
                    "logs": dict(_LAST_VALID_LOGS),
                    "last_known_telemetry": dict(_LAST_KNOWN_TELEMETRY),
                    "discovered_devices": sorted(list(_DISCOVERED_AWS_DEVICES), key=lambda x: int(x) if str(x).isdigit() else str(x))
                }
            parent_dir = os.path.dirname(SNAPSHOT_FILE)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            tid = threading.get_ident()
            tmp_file = f"{SNAPSHOT_FILE}.{tid}.{time.time_ns()}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp_file, SNAPSHOT_FILE)

            # Persist to PostgreSQL SystemCache so data is NEVER lost across cold starts/container deploys
            try:
                from app.database import SessionLocal
                from app.models.datalogger import SystemCache
                with SessionLocal() as db:
                    cache_row = db.query(SystemCache).filter(SystemCache.key == "aws_snapshot").first()
                    if not cache_row:
                        cache_row = SystemCache(key="aws_snapshot", data=data)
                        db.add(cache_row)
                    else:
                        cache_row.data = data
                    db.commit()
            except Exception as dbe:
                logger.debug(f"DB snapshot persist notice: {dbe}")
        except Exception as e:
            logger.warning(f"Error saving AWS telemetry snapshot: {e}")
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass

def _load_snapshot():
    global _LAST_VALID_DASHBOARD, _LAST_VALID_7DAY, _LAST_VALID_LOGS, _AWS_CACHE, _AWS_DAILY_SUMMARIES, _LAST_KNOWN_TELEMETRY, _DISCOVERED_AWS_DEVICES
    data = None

    # 1. Try PostgreSQL SystemCache first (always shared & persistent across deploys and cold starts)
    try:
        from app.database import SessionLocal
        from app.models.datalogger import SystemCache, DailyCowSummary
        with SessionLocal() as db:
            cache_row = db.query(SystemCache).filter(SystemCache.key == "aws_snapshot").first()
            if cache_row and cache_row.data:
                data = cache_row.data

            # Only sync AWS DailyCowSummary rows (prefixed with aws-) into _AWS_DAILY_SUMMARIES
            db_daily = db.query(DailyCowSummary).filter(DailyCowSummary.device_id.ilike("aws-%")).all()
            for row in db_daily:
                d_str = row.date.strftime("%Y-%m-%d")
                clean_dev_id = str(row.device_id).strip().lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
                if clean_dev_id not in _AWS_DAILY_SUMMARIES:
                    _AWS_DAILY_SUMMARIES[clean_dev_id] = {}
                prev = _AWS_DAILY_SUMMARIES[clean_dev_id].get(d_str, {})
                mon = max(prev.get("monitored_hours", 0.0), row.monitored_hours or 0.0)
                rum = max(prev.get("rum_hours", 0.0), row.rumination_hours or 0.0)
                lying = max(prev.get("lying_hours", 0.0), row.lying_hours or 0.0)
                feed = max(prev.get("feed_hours", 0.0), row.feeding_hours or 0.0)
                move = max(prev.get("move_hours", 0.0), row.moving_hours or 0.0)
                _AWS_DAILY_SUMMARIES[clean_dev_id][d_str] = {
                    "monitored_hours": mon,
                    "rum_hours": rum,
                    "lying_hours": lying,
                    "feed_hours": feed,
                    "move_hours": move,
                    "heat_count": row.heat_count or prev.get("heat_count", 0),
                    "total_packets": row.total_packets or prev.get("total_packets", 0),
                    "health_score": min(100, int((rum / 8.0) * 100)) if rum > 0 else 0,
                    "estrus_index": 0
                }
    except Exception as e:
        logger.warning(f"Error loading AWS snapshot from DB: {e}")

    # 2. Check disk file if DB had no snapshot yet
    if not data and os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                raw_content = f.read().strip()
                if raw_content:
                    data = json.loads(raw_content)
        except Exception as e:
            logger.warning(f"Error reading disk snapshot: {e}")

    if not data:
        return
    try:
        _LAST_VALID_DASHBOARD.update(data.get("dashboard", {}))
        _LAST_VALID_LOGS.update(data.get("logs", {}))
        _LAST_KNOWN_TELEMETRY.update(data.get("last_known_telemetry", {}))
        saved_devs = data.get("discovered_devices", [])
        if saved_devs:
            _DISCOVERED_AWS_DEVICES.update(str(x).strip() for x in saved_devs)

        # Merge daily summaries safely: NEVER overwrite positive data with zeroes
        saved_daily = data.get("daily_summaries", {})
        for dev_id, d_map in saved_daily.items():
            if dev_id not in _AWS_DAILY_SUMMARIES:
                _AWS_DAILY_SUMMARIES[dev_id] = {}
            for d_str, day_data in d_map.items():
                existing = _AWS_DAILY_SUMMARIES[dev_id].get(d_str)
                if not existing:
                    _AWS_DAILY_SUMMARIES[dev_id][d_str] = day_data
                else:
                    # Keep record with higher monitored_hours and packets
                    if (day_data.get("monitored_hours", 0.0) or 0) > (existing.get("monitored_hours", 0.0) or 0):
                        _AWS_DAILY_SUMMARIES[dev_id][d_str] = day_data

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
                mon_val = mons[i] if i < len(mons) else 0.0
                existing = _AWS_DAILY_SUMMARIES[dev_id].get(d_str)
                if not existing or mon_val > (existing.get("monitored_hours", 0.0) or 0):
                    _AWS_DAILY_SUMMARIES[dev_id][d_str] = {
                        "monitored_hours": mon_val,
                        "rum_hours": rums[i] if i < len(rums) else 0.0,
                        "lying_hours": lyings[i] if i < len(lyings) else 0.0,
                        "feed_hours": feeds[i] if i < len(feeds) else 0.0,
                        "move_hours": acts[i] if i < len(acts) else 0.0,
                        "health_score": scores[i] if i < len(scores) else 0,
                        "estrus_index": estrus[i] if i < len(estrus) else 0,
                        "heat_count": 0,
                        "total_packets": int((mon_val * 3600.0) / AWS_PACKET_INTERVAL_SECONDS) if i < len(mons) else 0
                    }

        # Validate 7-day data against current rolling 7-day window
        today_ist = datetime.now(IST).date()
        expected_dates = [(today_ist - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
        for dev_id, s7 in old_7day.items():
            if s7.get("dates") == expected_dates:
                # Check for 0.0 gaps that have data in _AWS_DAILY_SUMMARIES
                has_gap = False
                mons = s7.get("monitoredHours", [])
                for idx, d_str in enumerate(expected_dates):
                    mon_val = mons[idx] if idx < len(mons) else 0.0
                    known_sum = _AWS_DAILY_SUMMARIES.get(dev_id, {}).get(d_str, {})
                    if mon_val == 0.0 and (known_sum.get("monitored_hours", 0.0) or 0) > 0:
                        has_gap = True
                        break
                if not has_gap:
                    _LAST_VALID_7DAY[dev_id] = s7

        # Cache last known telemetry from saved dashboard if not present
        for dev_id, dash in _LAST_VALID_DASHBOARD.items():
            if dev_id not in _LAST_KNOWN_TELEMETRY and dash.get("liveTelemetry"):
                _LAST_KNOWN_TELEMETRY[dev_id] = {
                    "telemetry": dash["liveTelemetry"],
                    "accelBuffer": dash.get("accelBuffer"),
                    "timestamp": dash.get("liveTelemetry", {}).get("timestamp")
                }

        # Sanitize loaded dashboard against current day to prevent yesterday's data leaking into today
        for dev_id, dash in list(_LAST_VALID_DASHBOARD.items()):
            last_seen = dash.get("liveTelemetry", {}).get("timestamp")
            is_today = False
            if last_seen:
                try:
                    dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                    if dt.astimezone(IST).date() == today_ist:
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

        # Pre-warm fast in-memory activity logs cache from snapshot within active 7-day window
        cutoff_7d = (today_ist - timedelta(days=6)).strftime("%Y-%m-%d")
        today_str = today_ist.strftime("%Y-%m-%d")
        for dev_id, saved_logs_data in list(_LAST_VALID_LOGS.items()):
            l_list = saved_logs_data.get("logs", []) if isinstance(saved_logs_data, dict) else saved_logs_data
            if l_list:
                filtered_7d = [l for l in l_list if l.get("startTime", "")[:10] >= cutoff_7d]
                _LAST_VALID_LOGS[dev_id] = filtered_7d
                if filtered_7d:
                    act_cache_key = f"actlogs_{dev_id}_{today_str}"
                    _AWS_CACHE[act_cache_key] = {"expires_at": time.time() + 30.0, "data": filtered_7d}
        # Strict sanitization: purge any phantom devices that have 0 verified packets and no aws- DB rows
        verified_aws_ids = set()
        try:
            from app.database import SessionLocal
            from app.models.datalogger import DailyCowSummary
            with SessionLocal() as db:
                rows = db.query(DailyCowSummary.device_id).filter(
                    DailyCowSummary.device_id.ilike("aws-%"),
                    ((DailyCowSummary.total_packets > 0) | (DailyCowSummary.monitored_hours > 0))
                ).distinct().all()
                for (r_id,) in rows:
                    if r_id:
                        verified_aws_ids.add(str(r_id).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip())
        except Exception:
            pass

        for dev_k in list(_AWS_DAILY_SUMMARIES.keys()):
            clean_k = str(dev_k).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
            if clean_k not in verified_aws_ids and clean_k not in _DISCOVERED_AWS_DEVICES:
                _AWS_DAILY_SUMMARIES.pop(dev_k, None)

        for dev_k in list(_LAST_VALID_DASHBOARD.keys()):
            clean_k = str(dev_k).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
            if clean_k not in verified_aws_ids and clean_k not in _DISCOVERED_AWS_DEVICES:
                _LAST_VALID_DASHBOARD.pop(dev_k, None)

        for dev_k in list(_LAST_VALID_7DAY.keys()):
            clean_k = str(dev_k).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
            if clean_k not in verified_aws_ids and clean_k not in _DISCOVERED_AWS_DEVICES:
                _LAST_VALID_7DAY.pop(dev_k, None)

        for dev_k in list(_LAST_VALID_LOGS.keys()):
            clean_k = str(dev_k).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
            if clean_k not in verified_aws_ids and clean_k not in _DISCOVERED_AWS_DEVICES:
                _LAST_VALID_LOGS.pop(dev_k, None)

        for dev_k in list(_LAST_KNOWN_TELEMETRY.keys()):
            clean_k = str(dev_k).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
            if clean_k not in verified_aws_ids and clean_k not in _DISCOVERED_AWS_DEVICES:
                _LAST_KNOWN_TELEMETRY.pop(dev_k, None)

        for dev_k in list(_DISCOVERED_AWS_DEVICES):
            clean_k = str(dev_k).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
            if clean_k not in verified_aws_ids:
                _DISCOVERED_AWS_DEVICES.discard(dev_k)

        logger.info(f"Loaded persistent AWS telemetry snapshot with {len(_AWS_DAILY_SUMMARIES)} daily summary devices.")
    except Exception as e:
        logger.warning(f"Error loading AWS telemetry snapshot: {e}")
        try:
            if os.path.exists(SNAPSHOT_FILE):
                os.remove(SNAPSHOT_FILE)
        except Exception:
            pass

# In-memory caches for high-speed API performance
_AWS_CACHE: Dict[str, Dict[str, Any]] = {}
_HERD_ITEMS_CACHE: Dict[str, Any] = {"expires_at": 0.0, "data": []}
_METADATA_CACHE: Dict[str, Dict[str, Any]] = {}
_TAG_AWS_CACHE: Dict[str, Any] = {"expires_at": 0.0, "data": set()}
_ML_PREDICTION_CACHE: Dict[str, Any] = {}
_HERD_IS_REFRESHING = False
_REFRESH_THREAD_LOCK = threading.Lock()
_TAGS_LOADED_AT = 0.0
CACHE_TTL_SECONDS = 300

# Per-device locks to coalesce concurrent in-flight requests and prevent duplicate AWS calls
_IN_FLIGHT_DEVICE_LOCKS: Dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()

_AWS_HTTP_SESSION = None
_LIVE_REFRESHING_SET = set()
_LIVE_REFRESH_LOCK = threading.Lock()
_7DAY_REFRESHING_SET = set()
_7DAY_REFRESH_LOCK = threading.Lock()
_LOGS_REFRESHING_SET = set()
_LOGS_REFRESH_LOCK = threading.Lock()
_TELEMETRY_DAEMON_STARTED = False

def _get_aws_http_session():
    """Persistent requests.Session with connection pooling and keep-alive."""
    global _AWS_HTTP_SESSION
    if _AWS_HTTP_SESSION is None and _requests is not None:
        try:
            sess = _requests.Session()
            from requests.adapters import HTTPAdapter
            from urllib3.util import Retry
            retries = Retry(total=1, backoff_factor=0.1, status_forcelist=[502, 503, 504], raise_on_status=False)
            adapter = HTTPAdapter(pool_connections=25, pool_maxsize=35, max_retries=retries)
            sess.mount("https://", adapter)
            sess.mount("http://", adapter)
            _AWS_HTTP_SESSION = sess
        except Exception:
            _AWS_HTTP_SESSION = _requests.Session() if _requests else None
    return _AWS_HTTP_SESSION

def _get_device_lock(dev_id: str) -> threading.Lock:
    with _GLOBAL_LOCK:
        dev_key = str(dev_id).strip()
        if dev_key not in _IN_FLIGHT_DEVICE_LOCKS:
            _IN_FLIGHT_DEVICE_LOCKS[dev_key] = threading.Lock()
        return _IN_FLIGHT_DEVICE_LOCKS[dev_key]

# Load persistent snapshot immediately on module load
_load_snapshot()
_DISCOVERED_AWS_DEVICES.update(str(x).strip() for x in settings.AWS_ENABLED_DEVICE_IDS)

# Discovery state controls
_LAST_DISCOVERY_TIME = 0.0
_DISCOVERY_LOCK = threading.Lock()
_DISCOVERY_IN_PROGRESS = False
_DISCOVERY_DAEMON_STARTED = False

def _device_sort_key(dev_id: str):
    clean = str(dev_id).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
    return (0, int(clean)) if clean.isdigit() else (1, clean)


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
        now = datetime.now(IST)
        
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
                day_strs = []
                cur = s_dt
                while cur <= e_dt:
                    day_strs.append(cur.strftime("%d-%m-%Y"))
                    cur += timedelta(days=1)

                combined = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(day_strs))) as pool:
                    future_to_day = {pool.submit(AwsTelemetryService.fetch_aws_raw, device_id, start_date=d, end_date=d): d for d in day_strs}
                    # Keep sorted by date
                    day_pkts_map = {}
                    for fut in concurrent.futures.as_completed(future_to_day):
                        d = future_to_day[fut]
                        try:
                            day_pkts_map[d] = fut.result()
                        except Exception as e:
                            logger.warning(f"Error fetching day {d} for {device_id}: {e}")
                            day_pkts_map[d] = []
                    for d in day_strs:
                        combined.extend(day_pkts_map.get(d, []))
                return combined
            except Exception as e:
                logger.warning(f"Error expanding multi-day range {resolved_start}..{resolved_end}: {e}")

        cache_key = f"raw_{device_id}_{resolved_start}_{resolved_end}"
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"]

        base_url = settings.AWS_COWNECK_API_URL
        api_type = getattr(settings, "AWS_COWNECK_API_TYPE", "cow01")
        query_params = []
        if "type=" not in base_url and api_type:
            query_params.append(f"type={api_type}")
        query_params.append(f"deviceid={device_id}")
        query_params.append(f"startdate={resolved_start}")
        query_params.append(f"enddate={resolved_end}")

        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}{'&'.join(query_params)}"

        # Set generous read timeout (30s) so multi-thousand packet payloads (e.g. 1866 packets on busy days) never abort
        today_str = now.strftime("%d-%m-%Y")
        is_today = (resolved_start == today_str)
        read_timeout = 30

        try:
            sess = _get_aws_http_session()
            if sess is not None:
                resp = sess.get(
                    url,
                    headers={"User-Agent": "CowMonitoring-Backend/1.0", "Accept-Encoding": "gzip, deflate"},
                    timeout=(5, read_timeout),  # (connect_timeout, read_timeout)
                    stream=False
                )
                resp.raise_for_status()
                raw_bytes = resp.content
            elif _requests is not None:
                resp = _requests.get(
                    url,
                    headers={"User-Agent": "CowMonitoring-Backend/1.0", "Accept-Encoding": "gzip, deflate"},
                    timeout=(5, read_timeout),
                    stream=False
                )
                resp.raise_for_status()
                raw_bytes = resp.content
            else:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "CowMonitoring-Backend/1.0", "Accept-Encoding": "gzip, deflate"}
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
            # Cache failure briefly (15s) so background retries can succeed promptly
            fail_ttl = 15.0
            _AWS_CACHE[cache_key] = {
                "expires_at": time.time() + fail_ttl,
                "data": []
            }
            return []

    @classmethod
    def get_processed_packets(cls, device_id: str, start_date: str = None, end_date: str = None) -> List[dict]:
        """
        Fetches AWS packets and runs ML inference on each 80-sample window.
        Returns a list of parsed packets with their full ML inference results.
        Uses in-memory ML inference memoization to eliminate repeated calculations.
        Non-blocking: Network I/O runs outside thread locks.
        """
        cache_key = f"processed_{device_id}_{start_date}_{end_date}"
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"]

        # Fetch network packets asynchronously without blocking other read requests
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
        global _HERD_ITEMS_CACHE, _METADATA_CACHE, _TAGS_LOADED_AT, _TAG_AWS_CACHE
        _HERD_ITEMS_CACHE = {"expires_at": 0.0, "data": []}
        _METADATA_CACHE.clear()
        _TAGS_LOADED_AT = 0.0
        _TAG_AWS_CACHE = {"expires_at": 0.0, "data": set()}
        logger.info("Cleared AWS metadata & herd caches.")

    @classmethod
    def clear_all_telemetry_cache(cls):
        """Forces immediate wipe of telemetry caches and snapshots for fresh calculation."""
        global _AWS_CACHE, _LAST_VALID_DASHBOARD, _LAST_VALID_7DAY, _LAST_VALID_LOGS, _HERD_ITEMS_CACHE, _TAG_AWS_CACHE, _AWS_DAILY_SUMMARIES
        _AWS_CACHE.clear()
        _LAST_VALID_DASHBOARD.clear()
        _LAST_VALID_7DAY.clear()
        _LAST_VALID_LOGS.clear()
        _AWS_DAILY_SUMMARIES.clear()
        _HERD_ITEMS_CACHE = {"expires_at": 0.0, "data": []}
        _TAG_AWS_CACHE = {"expires_at": 0.0, "data": set()}
        if os.path.exists(SNAPSHOT_FILE):
            try:
                os.remove(SNAPSHOT_FILE)
            except Exception:
                pass
        logger.info("Cleared all AWS telemetry caches, daily summaries, and removed snapshot file.")

    @classmethod
    def get_known_device_ids(cls) -> List[str]:
        """
        Dynamically aggregates all known AWS device IDs:
        1. Auto-discovered active AWS device IDs from _DISCOVERED_AWS_DEVICES
        2. Devices in in-memory _AWS_DAILY_SUMMARIES
        3. Registered AWS tags from TagRegistry DB (cached for 60s)
        4. Devices with historical summaries in DailyCowSummary DB
        5. Configured seed IDs from settings.AWS_ENABLED_DEVICE_IDS (if any)
        """
        global _TAG_AWS_CACHE
        all_ids = set()
        for dev_id in settings.AWS_ENABLED_DEVICE_IDS:
            if dev_id:
                all_ids.add(str(dev_id).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip())
        for dev_id in _DISCOVERED_AWS_DEVICES:
            if dev_id:
                all_ids.add(str(dev_id).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip())
        for dev_id in _AWS_DAILY_SUMMARIES:
            if dev_id:
                all_ids.add(str(dev_id).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip())

        # Check TagRegistry and DailyCowSummary (cached for 60s)
        now_ts = time.time()
        if _TAG_AWS_CACHE.get("expires_at", 0) > now_ts:
            all_ids.update(_TAG_AWS_CACHE.get("data", set()))
        else:
            tag_ids = set()
            try:
                from app.database import SessionLocal
                from app.models.tag_registry import TagRegistry
                from app.models.datalogger import DailyCowSummary
                with SessionLocal() as db:
                    tags = db.query(TagRegistry.device_id, TagRegistry.notes).all()
                    for tag_dev_id, tag_notes in tags:
                        s = str(tag_dev_id).strip()
                        if s.lower().startswith("aws-") or s.lower().startswith("aws ") or s.lower().startswith("aws#"):
                            clean = s.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
                            tag_ids.add(clean)
                        elif tag_notes and "aws" in tag_notes.lower():
                            clean = s.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
                            tag_ids.add(clean)
                    # Include devices with existing DailyCowSummary rows explicitly belonging to AWS with data
                    daily_devs = db.query(DailyCowSummary.device_id).filter(
                        DailyCowSummary.device_id.ilike("aws-%"),
                        ((DailyCowSummary.total_packets > 0) | (DailyCowSummary.monitored_hours > 0))
                    ).distinct().all()
                    for (d_id,) in daily_devs:
                        if d_id:
                            clean = str(d_id).lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
                            tag_ids.add(clean)
                _TAG_AWS_CACHE = {"expires_at": now_ts + 60.0, "data": tag_ids}
                all_ids.update(tag_ids)
            except Exception:
                pass

        active_ids = [d for d in all_ids if cls.device_has_7day_data(d) or (d in _DISCOVERED_AWS_DEVICES)]
        return sorted(list(active_ids), key=_device_sort_key)

    @classmethod
    def is_aws_device(cls, cow_id: str) -> bool:
        """Determines if cow_id belongs to an AWS Collar node."""
        if not cow_id:
            return False
        s = str(cow_id).strip()
        s_clean = s.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
        if s.lower().startswith("aws-") or s.lower().startswith("aws ") or s.lower().startswith("aws#"):
            return cls.device_has_7day_data(s_clean) or (s_clean in _DISCOVERED_AWS_DEVICES)
        known = set(cls.get_known_device_ids())
        if s_clean in known:
            return True
        # On-demand probe if not yet known
        if cls.check_and_register_device(s_clean):
            return True
        return False

    @classmethod
    def check_and_register_device(cls, dev_id: str) -> bool:
        """
        Direct on-demand check if AWS has data for an individual device ID.
        If found, immediately registers it into _DISCOVERED_AWS_DEVICES, saves snapshot,
        and invalidates herd overview cache so it appears immediately.
        """
        if not dev_id:
            return False
        clean_id = str(dev_id).strip().lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
        if clean_id in _DISCOVERED_AWS_DEVICES:
            return True

        # Probe today, yesterday, and past days in the rolling 7-day window dynamically
        now_ist = datetime.now(IST)
        probe_dates = [(now_ist - timedelta(days=i)).strftime("%d-%m-%Y") for i in range(7)]
        for d_str in probe_dates:
            try:
                pkts = cls.fetch_aws_raw(clean_id, start_date=d_str, end_date=d_str)
                if pkts:
                    _DISCOVERED_AWS_DEVICES.add(clean_id)
                    _save_snapshot()
                    cls.clear_cache()
                    logger.info(f"On-demand auto-discovered active AWS device: {clean_id}")
                    return True
            except Exception as e:
                logger.debug(f"Probe error for device {clean_id} on {d_str}: {e}")
        return False

    @classmethod
    def discover_devices(cls, max_device_id: int = None, force: bool = False) -> List[str]:
        """
        Scans candidate AWS device IDs across range(1, max_device_id + 1) in parallel.
        Discovers any new active collar devices transmitting to AWS.
        Registers newly found devices, saves snapshot, and invalidates herd cache.
        """
        global _LAST_DISCOVERY_TIME, _DISCOVERY_IN_PROGRESS
        now_ts = time.time()

        with _DISCOVERY_LOCK:
            if _DISCOVERY_IN_PROGRESS:
                return []
            if not force and (now_ts - _LAST_DISCOVERY_TIME) < (settings.AWS_AUTO_DISCOVERY_INTERVAL_MINUTES * 60):
                return []
            _DISCOVERY_IN_PROGRESS = True

        try:
            scan_limit = max_device_id or settings.AWS_DISCOVERY_SCAN_MAX
            now_ist = datetime.now(IST)
            today_str = now_ist.strftime("%d-%m-%Y")
            yesterday_str = (now_ist - timedelta(days=1)).strftime("%d-%m-%Y")

            candidates = [str(i) for i in range(1, scan_limit + 1)]
            newly_found = []

            def probe_candidate(dev_str: str):
                for target_date in [today_str, yesterday_str]:
                    try:
                        pkts = cls.fetch_aws_raw(dev_str, start_date=target_date, end_date=target_date)
                        if pkts:
                            return dev_str, len(pkts)
                    except Exception:
                        pass
                return dev_str, 0

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                results = executor.map(probe_candidate, candidates)
                for dev_str, pkt_count in results:
                    if pkt_count > 0:
                        if dev_str not in _DISCOVERED_AWS_DEVICES:
                            _DISCOVERED_AWS_DEVICES.add(dev_str)
                            newly_found.append(dev_str)
                            logger.info(f"Auto-discovered new active AWS device ID {dev_str} ({pkt_count} packets).")

            _LAST_DISCOVERY_TIME = time.time()
            if newly_found:
                _save_snapshot()
                cls.clear_cache()
                logger.info(f"AWS auto-discovery completed. Added {len(newly_found)} new devices: {newly_found}")
            return newly_found
        except Exception as e:
            logger.error(f"Error during AWS auto-discovery scan: {e}")
            return []
        finally:
            with _DISCOVERY_LOCK:
                _DISCOVERY_IN_PROGRESS = False

    @classmethod
    def start_discovery_daemon(cls):
        """Starts periodic background discovery thread to auto-detect any newly added AWS collars."""
        global _DISCOVERY_DAEMON_STARTED
        with _DISCOVERY_LOCK:
            if _DISCOVERY_DAEMON_STARTED:
                return
            _DISCOVERY_DAEMON_STARTED = True

        def daemon_loop():
            # Initial discovery run shortly after server boot
            time.sleep(3)
            logger.info("Starting initial AWS device auto-discovery scan...")
            cls.discover_devices(force=True)

            while True:
                try:
                    interval_secs = max(60, settings.AWS_AUTO_DISCOVERY_INTERVAL_MINUTES * 60)
                    time.sleep(interval_secs)
                    cls.discover_devices()
                except Exception as e:
                    logger.warning(f"Error in AWS discovery daemon loop: {e}")
                    time.sleep(60)

        t = threading.Thread(target=daemon_loop, daemon=True, name="AwsDeviceAutoDiscoveryDaemon")
        t.start()
        logger.info("AWS device auto-discovery background daemon initialized.")

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
                    # Only apply TagRegistry records to AWS if explicitly marked as AWS (aws- prefix or notes)
                    is_aws_tag = dev_str.lower().startswith("aws-") or (tag.notes and "aws" in tag.notes.lower())
                    if not is_aws_tag:
                        continue
                    clean_id = dev_str.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
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

        # Ensure all configured & discovered AWS devices have default cache entries
        for dev_id in cls.get_known_device_ids():
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
    def _trigger_background_live_refresh(cls, clean_id: str, target_date: str):
        dev_key = str(clean_id).strip()
        with _LIVE_REFRESH_LOCK:
            if dev_key in _LIVE_REFRESHING_SET:
                return
            _LIVE_REFRESHING_SET.add(dev_key)

        def worker():
            try:
                cls._compute_live_dashboard(dev_key, target_date)
            except Exception as e:
                logger.warning(f"Error in background live refresh for dev {dev_key}: {e}")
            finally:
                with _LIVE_REFRESH_LOCK:
                    _LIVE_REFRESHING_SET.discard(dev_key)

        threading.Thread(target=worker, daemon=True, name=f"LiveRefresh-{dev_key}").start()

    @classmethod
    def _build_immediate_baseline_live(cls, clean_id: str) -> dict:
        """Instantly (<1ms) returns a valid live dashboard payload so HTTP requests never timeout."""
        dev_key = str(clean_id).strip()
        dev_meta = cls.get_device_metadata(clean_id)
        now = datetime.now(IST)
        today_date_str = now.strftime("%Y-%m-%d")

        today_sum = _AWS_DAILY_SUMMARIES.get(clean_id, {}).get(today_date_str, {})
        if not today_sum:
            try:
                from app.database import SessionLocal
                from app.models.datalogger import DailyCowSummary
                with SessionLocal() as db:
                    s_row = db.query(DailyCowSummary).filter(
                        DailyCowSummary.device_id == f"aws-{clean_id}",
                        DailyCowSummary.date == now.date()
                    ).first()
                    if s_row:
                        today_sum = {
                            "monitored_hours": s_row.monitored_hours or 0.0,
                            "rum_hours": s_row.rumination_hours or 0.0,
                            "lying_hours": s_row.lying_hours or 0.0,
                            "feed_hours": s_row.feeding_hours or 0.0,
                            "move_hours": s_row.moving_hours or 0.0,
                        }
            except Exception:
                pass

        mon_hrs = today_sum.get("monitored_hours", 0.0) or 0.0
        rum_hrs = today_sum.get("rum_hours", 0.0) or 0.0
        lying_hrs = today_sum.get("lying_hours", 0.0) or 0.0
        feed_hrs = today_sum.get("feed_hours", 0.0) or 0.0
        move_hrs = today_sum.get("move_hours", 0.0) or 0.0

        last_known = _LAST_KNOWN_TELEMETRY.get(clean_id) or _LAST_KNOWN_TELEMETRY.get(dev_key)
        last_telem = last_known["telemetry"] if last_known else {"x": 0, "y": 0, "z": 0, "magnitude": 0, "timestamp": now.isoformat()}
        last_accel = last_known["accelBuffer"] if last_known else {"labels": [f"{(i*0.1):.1f}s" for i in range(80)], "x": [0]*80, "y": [0]*80, "z": [0]*80, "mag": [0]*80}

        has_data = (mon_hrs > 0 or rum_hrs > 0)
        return {
            "cowId": f"aws-{clean_id}",
            "device_id": str(clean_id),
            "source": "aws_api",
            "cowName": dev_meta["name"],
            "tagNumber": dev_meta.get("tagNumber") or f"AWS {clean_id}",
            "breed": dev_meta["breed"],
            "location": dev_meta["location"],
            "weight": dev_meta["weight"],
            "notes": dev_meta["notes"],
            "isStale": not has_data,
            "currentActivity": {
                "code": "RUS" if has_data else None,
                "name": "Ruminating" if has_data else "No Recent Data",
                "color": "#06b6d4" if has_data else "#64748b",
                "icon": "fa-arrows-spin" if has_data else "fa-pause"
            },
            "healthStatus": {
                "monitoredHoursToday": mon_hrs,
                "ruminationHoursToday": rum_hrs,
                "lyingHoursToday": lying_hrs,
                "feedingHoursToday": feed_hrs,
                "movingHoursToday": move_hrs,
                "ruminationScore": min(100, int((rum_hrs / 8.0) * 100)) if rum_hrs > 0 else 0,
                "estrusProbabilityPercent": 0,
                "isHeatDetected": False,
                "healthRecommendation": "All health parameters within normal range." if has_data else "Awaiting live sensor packet uplink.",
                "health_risk_decision": "HEALTHY" if has_data else "NO_DATA"
            },
            "liveTelemetry": last_telem,
            "accelBuffer": last_accel,
            "ml_inference": {
                "ml_engine_status": "ACTIVE" if has_data else "OFFLINE",
                "activity": {"code": "RUS" if has_data else None, "confidence": 0.85 if has_data else 0.0},
                "heat_detection": {"in_heat": False, "heat_probability": 0.0, "alert_level": "NORMAL"},
                "anomaly_detection": {"is_anomaly": False, "score": 0.0},
                "health_risk_decision": "HEALTHY" if has_data else "NO_DATA"
            }
        }

    @classmethod
    def get_live_dashboard(cls, device_id: str, target_date: str = None) -> dict:
        """
        Builds the Live Diagnostics dashboard payload for an AWS device.
        Matches exact schema of get_cow_live_dashboard in cows.py.
        STRICTLY NON-BLOCKING: returns immediately (<2ms) from RAM/snapshot and refreshes in background.
        """
        now_ist = datetime.now(IST)
        today_date_str = now_ist.strftime("%d-%m-%Y")
        is_querying_today = (target_date is None or target_date == today_date_str)
        target = target_date or today_date_str
        dev_key = str(device_id).strip()
        clean_id = dev_key.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()

        cache_key = f"live_{clean_id}_{target}"
        now_ts = time.time()
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached.get("expires_at", 0) > now_ts:
            return cached["data"]

        # Stale-While-Revalidate: Return last valid computed dashboard immediately (<2ms)
        last_dash = _LAST_VALID_DASHBOARD.get(clean_id) or _LAST_VALID_DASHBOARD.get(dev_key)
        if is_querying_today and last_dash:
            d_str = now_ist.strftime("%Y-%m-%d")
            today_s = _AWS_DAILY_SUMMARIES.get(clean_id, {}).get(d_str) or _AWS_DAILY_SUMMARIES.get(dev_key, {}).get(d_str)
            if today_s and (today_s.get("monitored_hours", 0.0) or 0.0) > (last_dash.get("healthStatus", {}).get("monitoredHoursToday", 0.0) or 0.0):
                last_dash["healthStatus"]["monitoredHoursToday"] = today_s["monitored_hours"]
                last_dash["healthStatus"]["ruminationHoursToday"] = today_s.get("rum_hours", 0.0)
                last_dash["healthStatus"]["lyingHoursToday"] = today_s.get("lying_hours", 0.0)
                last_dash["healthStatus"]["feedingHoursToday"] = today_s.get("feed_hours", 0.0)
                last_dash["healthStatus"]["movingHoursToday"] = today_s.get("move_hours", 0.0)
            cls._trigger_background_live_refresh(clean_id, target)
            return last_dash

        # Strictly non-blocking baseline: Build immediate baseline, cache it, trigger background refresh, and return
        baseline = cls._build_immediate_baseline_live(clean_id)
        _LAST_VALID_DASHBOARD[clean_id] = baseline
        _LAST_VALID_DASHBOARD[dev_key] = baseline
        cls._trigger_background_live_refresh(clean_id, target)
        return baseline

    @classmethod
    def _calculate_day_metrics(cls, pkts: list) -> dict:
        """
        Unified single-source-of-truth calculation for daily livestock behavior metrics.
        Used identically by Live Diagnostics, 7-Day Analytics, and Node Directory.
        """
        tot = len(pkts)
        if tot == 0:
            return {
                "total_packets": 0,
                "monitored_hours": 0.0,
                "rum_hours": 0.0,
                "lying_hours": 0.0,
                "feed_hours": 0.0,
                "move_hours": 0.0,
                "heat_count": 0,
                "counts": {"RUS": 0, "REL": 0, "FEP": 0, "MOV": 0, "RES": 0, "HEAT": 0},
                "health_score": 0,
                "estrus_index": 0
            }

        first_epoch = pkts[0].get("epoch") or (pkts[0]["timestamp"].timestamp() if pkts[0].get("timestamp") else 0)
        last_epoch = pkts[-1].get("epoch") or (pkts[-1]["timestamp"].timestamp() if pkts[-1].get("timestamp") else 0)
        
        first_dt = datetime.fromtimestamp(first_epoch, tz=IST) if first_epoch > 0 else None
        last_dt = datetime.fromtimestamp(last_epoch, tz=IST) if last_epoch > 0 else None
        now_ist = datetime.now(IST)

        # Check if this day is today in IST
        is_today = bool((first_dt and first_dt.date() == now_ist.date()) or (last_dt and last_dt.date() == now_ist.date()))

        if is_today:
            midnight_today = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
            day_cap = max(0.1, (now_ist - midnight_today).total_seconds() / 3600.0)
        else:
            day_cap = 24.0

        # Calculate time span of actual observations throughout the day
        if last_epoch >= first_epoch and first_epoch > 0:
            # Check for large offline gaps (> 30 minutes)
            total_offline_secs = 0.0
            if tot > 1:
                for i in range(1, tot):
                    prev_ep = pkts[i-1].get("epoch") or (pkts[i-1]["timestamp"].timestamp() if pkts[i-1].get("timestamp") else 0)
                    curr_ep = pkts[i].get("epoch") or (pkts[i]["timestamp"].timestamp() if pkts[i].get("timestamp") else 0)
                    gap = curr_ep - prev_ep
                    if gap > 1800:  # > 30 mins indicates collar was offline / disconnected
                        total_offline_secs += (gap - 180)

            active_secs = max(0.0, (last_epoch - first_epoch) - total_offline_secs)
            span_hrs = (active_secs + AWS_PACKET_INTERVAL_SECONDS) / 3600.0

            if tot >= 10:
                # Device is periodically transmitting samples across the observation window
                mon_hrs = min(day_cap, span_hrs)
            else:
                # Sparse packets: credit packet count or span, whichever is bounded
                packet_hrs = (tot * AWS_PACKET_INTERVAL_SECONDS) / 3600.0
                mon_hrs = min(day_cap, max(span_hrs, packet_hrs))
        else:
            packet_hrs = (tot * AWS_PACKET_INTERVAL_SECONDS) / 3600.0
            mon_hrs = min(day_cap, packet_hrs)

        mon_hrs = round(min(day_cap, max(0.0, mon_hrs)), 2)

        counts = {"RUS": 0, "REL": 0, "FEP": 0, "MOV": 0, "RES": 0, "HEAT": 0}
        for p in pkts:
            inf = p.get("ml_inference", {})
            act_info = inf.get("activity", {})
            code = act_info.get("code")
            if code == "RUS":
                counts["RUS"] += 1
            elif code == "REL":
                counts["REL"] += 1
            elif code in ["FEP", "FED", "GRZ"]:
                counts["FEP"] += 1
            elif code == "MOV":
                counts["MOV"] += 1
            elif code == "RES":
                counts["RES"] += 1

            if inf.get("heat_detection", {}).get("in_heat"):
                counts["HEAT"] += 1

        r_hrs = min(mon_hrs, round((counts["RUS"] / tot) * mon_hrs, 2))
        l_hrs = min(mon_hrs, round((counts["REL"] / tot) * mon_hrs, 2))
        f_hrs = min(mon_hrs, round((counts["FEP"] / tot) * mon_hrs, 2))
        m_hrs = min(mon_hrs, round((counts["MOV"] / tot) * mon_hrs, 2))

        if mon_hrs >= 4.0:
            h_score = min(100, int((r_hrs / 8.0) * 100)) if r_hrs > 0 else (50 if (l_hrs > 0 or f_hrs > 0) else 0)
        elif mon_hrs > 0:
            rum_ratio = r_hrs / mon_hrs
            h_score = min(100, max(25, int((rum_ratio / 0.35) * 80))) if r_hrs > 0 else (50 if (l_hrs > 0 or f_hrs > 0) else 20)
        else:
            h_score = 0

        e_idx = int((counts["HEAT"] / tot) * 100)

        return {
            "total_packets": tot,
            "monitored_hours": mon_hrs,
            "rum_hours": r_hrs,
            "lying_hours": l_hrs,
            "feed_hours": f_hrs,
            "move_hours": m_hrs,
            "heat_count": counts["HEAT"],
            "counts": counts,
            "health_score": h_score,
            "estrus_index": min(100, e_idx)
        }

    @classmethod
    def _compute_live_dashboard(cls, device_id: str, target_date: str = None) -> dict:
        now_ist = datetime.now(IST)
        today_date_str = now_ist.strftime("%d-%m-%Y")
        is_querying_today = (target_date is None or target_date == today_date_str)
        target = target_date or today_date_str
        dev_key = str(device_id).strip()
        clean_id = dev_key.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
        cache_key = f"live_{clean_id}_{target}"

        packets = cls.get_processed_packets(clean_id, start_date=target, end_date=target)
        dev_meta = cls.get_device_metadata(clean_id)

        # Filter packets strictly belonging to target date in IST
        target_date_obj = datetime.strptime(target, "%d-%m-%Y").date()
        target_packets = [p for p in packets if p["timestamp"].astimezone(IST).date() == target_date_obj]
        if not target_packets:
            target_packets = packets

        # If device has no packets for this target date (e.g. today has no data)
        if not target_packets:
            last_known = _LAST_KNOWN_TELEMETRY.get(clean_id) or _LAST_KNOWN_TELEMETRY.get(dev_key)
            last_telem = last_known["telemetry"] if last_known else {"x": 0, "y": 0, "z": 0, "magnitude": 0, "timestamp": now_ist.isoformat()}
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
                "cowId": f"aws-{clean_id}",
                "device_id": str(clean_id),
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
                    "healthRecommendation": "No sensor telemetry received today for this collar node. Metrics and diagnostics will activate when fresh data arrives.",
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
            _LAST_VALID_DASHBOARD[clean_id] = empty_res
            _LAST_VALID_DASHBOARD[dev_key] = empty_res
            _save_snapshot()
            _AWS_CACHE[cache_key] = {"expires_at": time.time() + 60.0, "data": empty_res}
            return empty_res

        # Latest packet of target date is the last one in the sorted list
        latest = target_packets[-1]
        latest_ts = latest["timestamp"]
        
        # Check staleness in IST
        is_stale = (now_ist - latest_ts.astimezone(IST)).total_seconds() > (24 * 3600)

        # Call unified metrics calculation
        metrics = cls._calculate_day_metrics(target_packets)
        monitored_hours = metrics["monitored_hours"]
        rum_hrs = metrics["rum_hours"]
        lying_hrs = metrics["lying_hours"]
        feed_hrs = metrics["feed_hours"]
        move_hrs = metrics["move_hours"]
        counts = metrics["counts"]

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
            "cowId": f"aws-{clean_id}",
            "device_id": str(clean_id),
            "source": "aws_api",
            "cowName": dev_meta["name"],
            "tagNumber": dev_meta.get("tagNumber") or f"AWS {clean_id}",
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
                "ruminationScore": metrics["health_score"],
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
        _LAST_VALID_DASHBOARD[clean_id] = live_payload
        _LAST_VALID_DASHBOARD[dev_key] = live_payload
        _LAST_KNOWN_TELEMETRY[clean_id] = {
            "telemetry": live_payload["liveTelemetry"],
            "accelBuffer": live_payload["accelBuffer"],
            "timestamp": latest_ts.isoformat()
        }
        _LAST_KNOWN_TELEMETRY[dev_key] = _LAST_KNOWN_TELEMETRY[clean_id]

        # Atomically synchronize across all pages:
        d_str = target_date_obj.strftime("%Y-%m-%d")
        if clean_id not in _AWS_DAILY_SUMMARIES:
            _AWS_DAILY_SUMMARIES[clean_id] = {}
        _AWS_DAILY_SUMMARIES[clean_id][d_str] = metrics
        if dev_key not in _AWS_DAILY_SUMMARIES:
            _AWS_DAILY_SUMMARIES[dev_key] = {}
        _AWS_DAILY_SUMMARIES[dev_key][d_str] = metrics

        # Synchronize today's bar in _LAST_VALID_7DAY
        for target_key in [clean_id, dev_key]:
            cached_7d = _LAST_VALID_7DAY.get(target_key)
            if cached_7d and "dates" in cached_7d and d_str in cached_7d["dates"]:
                try:
                    d_idx = cached_7d["dates"].index(d_str)
                    cached_7d["monitoredHours"][d_idx] = monitored_hours
                    cached_7d["ruminationHours"][d_idx] = rum_hrs
                    cached_7d["lyingRestHours"][d_idx] = lying_hrs
                    cached_7d["feedingHours"][d_idx] = feed_hrs
                    cached_7d["activeHours"][d_idx] = move_hrs
                    cached_7d["healthScores"][d_idx] = metrics["health_score"]
                except Exception:
                    pass

        # Persist today's summary to PostgreSQL DailyCowSummary
        try:
            from app.database import SessionLocal
            from app.models.datalogger import DailyCowSummary
            with SessionLocal() as db:
                aws_db_id = f"aws-{clean_id}"
                existing_row = db.query(DailyCowSummary).filter(
                    DailyCowSummary.device_id == aws_db_id,
                    DailyCowSummary.date == target_date_obj
                ).first()
                if not existing_row:
                    db.add(DailyCowSummary(
                        device_id=aws_db_id,
                        date=target_date_obj,
                        total_packets=metrics["total_packets"],
                        monitored_hours=monitored_hours,
                        rumination_hours=rum_hrs,
                        lying_hours=lying_hrs,
                        feeding_hours=feed_hrs,
                        moving_hours=move_hrs,
                        heat_count=metrics["heat_count"]
                    ))
                else:
                    existing_row.total_packets = metrics["total_packets"]
                    existing_row.monitored_hours = monitored_hours
                    existing_row.rumination_hours = rum_hrs
                    existing_row.lying_hours = lying_hrs
                    existing_row.feeding_hours = feed_hrs
                    existing_row.moving_hours = move_hrs
                    existing_row.heat_count = metrics["heat_count"]
                db.commit()
        except Exception as dbe:
            logger.debug(f"DB live summary persist notice: {dbe}")

        _HERD_ITEMS_CACHE["expires_at"] = 0.0
        _save_snapshot()
        _AWS_CACHE[cache_key] = {"expires_at": time.time() + 60.0, "data": live_payload}
        return live_payload

    @classmethod
    def _update_daily_summary_from_packets(cls, dev_id: str, d: date, pkts: list):
        """Update _AWS_DAILY_SUMMARIES for a specific device and date."""
        dev_key = str(dev_id).strip()
        clean_id = dev_key.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
        d_str = d.strftime("%Y-%m-%d")
        if clean_id not in _AWS_DAILY_SUMMARIES:
            _AWS_DAILY_SUMMARIES[clean_id] = {}
        if dev_key not in _AWS_DAILY_SUMMARIES:
            _AWS_DAILY_SUMMARIES[dev_key] = {}

        if not pkts:
            existing = _AWS_DAILY_SUMMARIES[clean_id].get(d_str)
            if existing and ((existing.get("monitored_hours", 0) or 0) > 0 or (existing.get("total_packets", 0) or 0) > 0):
                return
            empty_m = cls._calculate_day_metrics([])
            _AWS_DAILY_SUMMARIES[clean_id][d_str] = empty_m
            _AWS_DAILY_SUMMARIES[dev_key][d_str] = empty_m
            return

        metrics = cls._calculate_day_metrics(pkts)
        _AWS_DAILY_SUMMARIES[clean_id][d_str] = metrics
        _AWS_DAILY_SUMMARIES[dev_key][d_str] = metrics

    @classmethod
    def _trigger_background_7day_refresh(cls, clean_id: str):
        dev_key = str(clean_id).strip()
        with _7DAY_REFRESH_LOCK:
            if dev_key in _7DAY_REFRESHING_SET:
                return
            _7DAY_REFRESHING_SET.add(dev_key)

        def worker():
            try:
                cls._refresh_7day_and_logs(dev_key)
            except Exception as e:
                logger.warning(f"Error in background 7day refresh for dev {dev_key}: {e}")
            finally:
                with _7DAY_REFRESH_LOCK:
                    _7DAY_REFRESHING_SET.discard(dev_key)

        threading.Thread(target=worker, daemon=True, name=f"7DayRefresh-{dev_key}").start()

    @classmethod
    def _trigger_background_logs_refresh(cls, clean_id: str):
        dev_key = str(clean_id).strip()
        with _LOGS_REFRESH_LOCK:
            if dev_key in _LOGS_REFRESHING_SET:
                return
            _LOGS_REFRESHING_SET.add(dev_key)

        def worker():
            try:
                cls._refresh_7day_and_logs(dev_key)
            except Exception as e:
                logger.warning(f"Error in background logs refresh for dev {dev_key}: {e}")
            finally:
                with _LOGS_REFRESH_LOCK:
                    _LOGS_REFRESHING_SET.discard(dev_key)

        threading.Thread(target=worker, daemon=True, name=f"LogsRefresh-{dev_key}").start()

    @classmethod
    def _build_immediate_baseline_7day(cls, clean_id: str, dev_key: str) -> dict:
        """Instantly (<1ms) construct a valid 7-day structure so the UI never blocks or times out."""
        now_ist = datetime.now(IST)
        today = now_ist.date()
        date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]
        day_labels = [d.strftime("%a") for d in date_range]
        date_labels = [d.strftime("%Y-%m-%d") for d in date_range]

        dash = _LAST_VALID_DASHBOARD.get(clean_id) or _LAST_VALID_DASHBOARD.get(dev_key) or _LAST_VALID_DASHBOARD.get(f"aws-{clean_id}") or {}
        health = dash.get("healthStatus", {})
        today_mon = health.get("monitoredHoursToday", 0.0) or 0.0
        today_rum = health.get("ruminationHoursToday", 0.0) or 0.0
        today_lying = health.get("lyingHoursToday", 0.0) or 0.0
        today_feed = health.get("feedingHoursToday", 0.0) or 0.0
        today_move = health.get("movingHoursToday", 0.0) or 0.0
        today_score = health.get("ruminationScore", 0) or 0
        today_estrus = health.get("estrusProbabilityPercent", 0) or 0

        rum_list, lying_list, feed_list, act_list = [], [], [], []
        monitored_list, health_score_list, estrus_index_list = [], [], []

        for d in date_range:
            d_str = d.strftime("%Y-%m-%d")
            s = _AWS_DAILY_SUMMARIES.get(clean_id, {}).get(d_str)
            if not s or ((s.get("monitored_hours", 0.0) or 0) == 0 and (s.get("total_packets", 0) or 0) == 0):
                try:
                    from app.database import SessionLocal
                    from app.models.datalogger import DailyCowSummary
                    with SessionLocal() as db:
                        row = db.query(DailyCowSummary).filter(
                            DailyCowSummary.device_id == f"aws-{clean_id}",
                            DailyCowSummary.date == d
                        ).first()
                        if row and ((row.monitored_hours or 0) > 0 or (row.total_packets or 0) > 0):
                            s = {
                                "monitored_hours": row.monitored_hours or 0.0,
                                "rum_hours": row.rumination_hours or 0.0,
                                "lying_hours": row.lying_hours or 0.0,
                                "feed_hours": row.feeding_hours or 0.0,
                                "move_hours": row.moving_hours or 0.0,
                                "total_packets": row.total_packets or 0,
                                "heat_count": row.heat_count or 0,
                                "health_score": min(100, int(((row.rumination_hours or 0.0) / 8.0) * 100)) if (row.rumination_hours or 0.0) > 0 else 0,
                                "estrus_index": 0
                            }
                            if clean_id not in _AWS_DAILY_SUMMARIES:
                                _AWS_DAILY_SUMMARIES[clean_id] = {}
                            _AWS_DAILY_SUMMARIES[clean_id][d_str] = s
                except Exception:
                    pass

            if s:
                rum_list.append(s.get("rum_hours", 0.0) or 0.0)
                lying_list.append(s.get("lying_hours", 0.0) or 0.0)
                feed_list.append(s.get("feed_hours", 0.0) or 0.0)
                act_list.append(s.get("move_hours", 0.0) or 0.0)
                monitored_list.append(s.get("monitored_hours", 0.0) or 0.0)
                health_score_list.append(s.get("health_score", 0) or 0)
                estrus_index_list.append(s.get("estrus_index", 0) or 0)
            elif d == today:
                rum_list.append(today_rum)
                lying_list.append(today_lying)
                feed_list.append(today_feed)
                act_list.append(today_move)
                monitored_list.append(today_mon)
                health_score_list.append(today_score)
                estrus_index_list.append(today_estrus)
            else:
                rum_list.append(0.0)
                lying_list.append(0.0)
                feed_list.append(0.0)
                act_list.append(0.0)
                monitored_list.append(0.0)
                health_score_list.append(0)
                estrus_index_list.append(0)

        weekly_avg = {
            "RUS": round(sum(rum_list) / 7.0, 4),
            "REL": round(sum(lying_list) / 7.0, 4),
            "FEP": round(sum(feed_list) / 7.0, 4),
            "MOV": round(sum(act_list) / 7.0, 4),
            "RES": 0.0,
            "DRN": 0.0
        }

        return {
            "cowId": f"aws-{clean_id}",
            "device_id": str(clean_id),
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

    @classmethod
    def get_7day_activity(cls, device_id: str) -> dict:
        """
        Builds the 7-day behavior distribution for an AWS device.
        STRICTLY NON-BLOCKING: Returns immediately from cache or snapshot (<2ms) and refreshes in background.
        """
        dev_key = str(device_id).strip()
        clean_id = dev_key.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
        now_ist = datetime.now(IST)
        today = now_ist.date()
        today_str = today.strftime("%Y-%m-%d")

        cache_key = f"7day_{clean_id}_{today_str}"
        now_ts = time.time()
        cached = _AWS_CACHE.get(cache_key)
        if cached and cached.get("expires_at", 0) > now_ts:
            return cached["data"]

        # Stale-While-Revalidate: Return last valid 7day immediately (<2ms) if up-to-date
        date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]
        expected_dates = [d.strftime("%Y-%m-%d") for d in date_range]
        last_7d = _LAST_VALID_7DAY.get(clean_id) or _LAST_VALID_7DAY.get(dev_key)

        is_valid_7d = False
        if last_7d and last_7d.get("dates") == expected_dates:
            has_gap = False
            mons = last_7d.get("monitoredHours", [])
            for idx, d_str in enumerate(expected_dates):
                mon_val = mons[idx] if idx < len(mons) else 0.0
                known_s = _AWS_DAILY_SUMMARIES.get(clean_id, {}).get(d_str, {})
                known_mon = known_s.get("monitored_hours", 0.0) or 0.0
                if mon_val == 0.0 and known_mon > 0:
                    has_gap = True
                    break
            if not has_gap:
                is_valid_7d = True

        if is_valid_7d:
            d_str = today.strftime("%Y-%m-%d")
            today_s = _AWS_DAILY_SUMMARIES.get(clean_id, {}).get(d_str) or _AWS_DAILY_SUMMARIES.get(dev_key, {}).get(d_str)
            last_dash = _LAST_VALID_DASHBOARD.get(clean_id) or _LAST_VALID_DASHBOARD.get(dev_key)
            best_mon = last_7d.get("monitoredHours", [])[-1] if last_7d.get("monitoredHours") else 0.0
            best_rum = last_7d.get("ruminationHours", [])[-1] if last_7d.get("ruminationHours") else 0.0
            if today_s:
                if (today_s.get("monitored_hours", 0.0) or 0.0) > best_mon:
                    best_mon = today_s["monitored_hours"]
                    best_rum = today_s.get("rum_hours", 0.0)
            if last_dash:
                dash_mon = last_dash.get("healthStatus", {}).get("monitoredHoursToday", 0.0) or 0.0
                if dash_mon > best_mon:
                    best_mon = dash_mon
                    best_rum = last_dash.get("healthStatus", {}).get("ruminationHoursToday", 0.0) or 0.0
            if best_mon > 0 and last_7d.get("monitoredHours"):
                last_7d["monitoredHours"][-1] = best_mon
                last_7d["ruminationHours"][-1] = best_rum
                if last_dash and "healthStatus" in last_dash:
                    last_dash["healthStatus"]["monitoredHoursToday"] = best_mon
                    last_dash["healthStatus"]["ruminationHoursToday"] = best_rum
            cls._trigger_background_7day_refresh(clean_id)
            return last_7d

        # Strictly non-blocking baseline: Build immediate baseline from daily summaries & DB, cache it, trigger background refresh, and return
        baseline = cls._build_immediate_baseline_7day(clean_id, dev_key)
        _LAST_VALID_7DAY[clean_id] = baseline
        _LAST_VALID_7DAY[dev_key] = baseline
        _AWS_CACHE[cache_key] = {"expires_at": time.time() + 60.0, "data": baseline}
        cls._trigger_background_7day_refresh(clean_id)
        return baseline

    @classmethod
    def _compute_7day_activity(cls, device_id: str) -> dict:
        return cls._refresh_7day_and_logs(device_id)

    @classmethod
    def _refresh_7day_and_logs(cls, device_id: str) -> dict:
        """
        Optimized 7-day pipeline:
        1. Fetches today's live packets from AWS API.
        2. Reuses immutable historical summaries from PostgreSQL / RAM (skips slow AWS calls).
        3. Persists updated daily summaries to PostgreSQL DailyCowSummary table.
        4. Chronologically merges transition logs and updates snapshot.
        """
        dev_key = str(device_id).strip()
        clean_id = dev_key.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
        now_ist = datetime.now(IST)
        today = now_ist.date()
        today_str = today.strftime("%Y-%m-%d")

        date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]
        day_labels = [d.strftime("%a") for d in date_range]
        date_labels = [d.strftime("%Y-%m-%d") for d in date_range]

        # 1. Fetch TODAY's packets from AWS API
        today_aws_fmt = today.strftime("%d-%m-%Y")
        today_packets = cls.get_processed_packets(clean_id, start_date=today_aws_fmt, end_date=today_aws_fmt)
        if today_packets:
            cls._update_daily_summary_from_packets(clean_id, today, today_packets)

        # 2. Check past days: if already in _AWS_DAILY_SUMMARIES or PostgreSQL DailyCowSummary with data, reuse!
        missing_past_days = []
        for d in date_range[:-1]:  # exclude today
            d_str = d.strftime("%Y-%m-%d")
            s = _AWS_DAILY_SUMMARIES.get(clean_id, {}).get(d_str)
            if not s or s.get("monitored_hours", 0.0) == 0:
                try:
                    from app.database import SessionLocal
                    from app.models.datalogger import DailyCowSummary
                    with SessionLocal() as db:
                        row = db.query(DailyCowSummary).filter(
                            DailyCowSummary.device_id == f"aws-{clean_id}",
                            DailyCowSummary.date == d
                        ).first()
                        if row and (row.monitored_hours or 0) > 0:
                            if clean_id not in _AWS_DAILY_SUMMARIES:
                                _AWS_DAILY_SUMMARIES[clean_id] = {}
                            _AWS_DAILY_SUMMARIES[clean_id][d_str] = {
                                "monitored_hours": row.monitored_hours,
                                "rum_hours": row.rumination_hours or 0.0,
                                "lying_hours": row.lying_hours or 0.0,
                                "feed_hours": row.feeding_hours or 0.0,
                                "move_hours": row.moving_hours or 0.0,
                                "heat_count": row.heat_count or 0,
                                "total_packets": row.total_packets or 0,
                                "health_score": min(100, int(((row.rumination_hours or 0.0) / 8.0) * 100)) if (row.rumination_hours or 0.0) > 0 else 0,
                                "estrus_index": 0
                            }
                            continue
                except Exception:
                    pass
                missing_past_days.append(d)

        # Fetch all missing past days (runs in background worker thread)
        if missing_past_days:
            for d in missing_past_days:
                d_aws_fmt = d.strftime("%d-%m-%Y")
                try:
                    pkts = cls.get_processed_packets(clean_id, start_date=d_aws_fmt, end_date=d_aws_fmt)
                    if pkts:
                        cls._update_daily_summary_from_packets(clean_id, d, pkts)
                except Exception as e:
                    logger.warning(f"Past day fetch error {d_aws_fmt} for dev {clean_id}: {e}")

        # 3. Persist updated daily summaries to PostgreSQL DailyCowSummary
        try:
            from app.database import SessionLocal
            from app.models.datalogger import DailyCowSummary
            with SessionLocal() as db:
                aws_db_id = f"aws-{clean_id}"
                for d in date_range:
                    d_str = d.strftime("%Y-%m-%d")
                    s = _AWS_DAILY_SUMMARIES.get(clean_id, {}).get(d_str)
                    if s and (s.get("monitored_hours", 0) > 0 or s.get("rum_hours", 0) > 0):
                        existing = db.query(DailyCowSummary).filter(
                            DailyCowSummary.device_id == aws_db_id,
                            DailyCowSummary.date == d
                        ).first()
                        if not existing:
                            db.add(DailyCowSummary(
                                device_id=aws_db_id,
                                date=d,
                                total_packets=s.get("total_packets", 0),
                                monitored_hours=s.get("monitored_hours", 0.0),
                                rumination_hours=s.get("rum_hours", 0.0),
                                lying_hours=s.get("lying_hours", 0.0),
                                feeding_hours=s.get("feed_hours", 0.0),
                                moving_hours=s.get("move_hours", 0.0),
                                heat_count=s.get("heat_count", 0)
                            ))
                        else:
                            existing.total_packets = s.get("total_packets", existing.total_packets)
                            existing.monitored_hours = s.get("monitored_hours", 0.0)
                            existing.rumination_hours = s.get("rum_hours", 0.0)
                            existing.lying_hours = s.get("lying_hours", 0.0)
                            existing.feeding_hours = s.get("feed_hours", 0.0)
                            existing.moving_hours = s.get("move_hours", 0.0)
                            existing.heat_count = s.get("heat_count", 0)
                db.commit()
        except Exception as e:
            logger.debug(f"DB daily summary sync notice: {e}")

        # 4. Build 7-day metric arrays
        rum_list, lying_list, feed_list, act_list = [], [], [], []
        monitored_list, health_score_list, estrus_index_list = [], [], []

        for d in date_range:
            d_str = d.strftime("%Y-%m-%d")
            s = _AWS_DAILY_SUMMARIES.get(clean_id, {}).get(d_str, {
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

        result_7d = {
            "cowId": f"aws-{clean_id}",
            "device_id": str(clean_id),
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

        _LAST_VALID_7DAY[clean_id] = result_7d
        _LAST_VALID_7DAY[dev_key] = result_7d
        cache_key_7d = f"7day_{clean_id}_{today_str}"
        _AWS_CACHE[cache_key_7d] = {"expires_at": time.time() + 60.0, "data": result_7d}

        # Atomically synchronize Live Diagnostics dashboard health status with today's metrics
        s_today = _AWS_DAILY_SUMMARIES.get(clean_id, {}).get(today_str)
        if s_today:
            dash = _LAST_VALID_DASHBOARD.get(clean_id) or _LAST_VALID_DASHBOARD.get(dev_key)
            if dash and "healthStatus" in dash:
                dash["healthStatus"].update({
                    "monitoredHoursToday": s_today["monitored_hours"],
                    "ruminationHoursToday": s_today["rum_hours"],
                    "lyingHoursToday": s_today["lying_hours"],
                    "feedingHoursToday": s_today["feed_hours"],
                    "movingHoursToday": s_today["move_hours"],
                    "ruminationScore": s_today["health_score"]
                })

        # 5. Build chronological transition logs from today_packets and merge with existing logs
        if today_packets:
            today_packets.sort(key=lambda p: p["timestamp"])
            grouped_logs = []
            current_group = None
            last_ts = None

            for idx, p in enumerate(today_packets):
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
                        "logId": f"aws-{clean_id}-{idx+1}",
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

            # Merge with existing logs for this device
            min_date_str = date_range[0].strftime("%Y-%m-%d")
            existing = _LAST_VALID_LOGS.get(clean_id, []) or _LAST_VALID_LOGS.get(dev_key, [])
            if isinstance(existing, dict):
                existing = existing.get("logs", [])
            if existing:
                new_dates = set(l["startTime"][:10] for l in grouped_logs if l.get("startTime"))
                for old_log in existing:
                    old_date = old_log.get("startTime", "")[:10]
                    if old_date and old_date >= min_date_str and old_date not in new_dates:
                        grouped_logs.append(old_log)

            grouped_logs = [l for l in grouped_logs if l.get("startTime", "")[:10] >= min_date_str]
            grouped_logs.sort(key=lambda x: x.get("startTime", ""), reverse=True)
            if grouped_logs:
                _LAST_VALID_LOGS[clean_id] = grouped_logs
                _LAST_VALID_LOGS[dev_key] = grouped_logs

            cache_key_logs = f"actlogs_{clean_id}_{today_str}"
            _AWS_CACHE[cache_key_logs] = {"expires_at": time.time() + 60.0, "data": grouped_logs}

        _HERD_ITEMS_CACHE["expires_at"] = 0.0
        _save_snapshot()
        return result_7d

    @classmethod
    def get_activity_logs(cls, device_id: str, page: int = 1, limit: int = 20) -> dict:
        """
        Builds chronological activity transition logs for an AWS device across the 7-day window.
        STRICTLY NON-BLOCKING: Returns immediately from cache or snapshot (<2ms) and refreshes in background.
        """
        dev_key = str(device_id).strip()
        clean_id = dev_key.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
        now = datetime.now(IST)
        today = now.date()

        cache_key = f"actlogs_{clean_id}_{today.strftime('%Y-%m-%d')}"
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

        last_logs = _LAST_VALID_LOGS.get(clean_id) or _LAST_VALID_LOGS.get(dev_key)
        if not last_logs:
            # Check PostgreSQL SystemCache for persistent logs
            try:
                from app.database import SessionLocal
                from app.models.datalogger import SystemCache
                with SessionLocal() as db:
                    sc = db.query(SystemCache).filter(SystemCache.key == "aws_snapshot").first()
                    if sc and sc.data:
                        db_logs = sc.data.get("logs", {}).get(clean_id, [])
                        if db_logs:
                            last_logs = db_logs
                            _LAST_VALID_LOGS[clean_id] = db_logs
                            _LAST_VALID_LOGS[dev_key] = db_logs
            except Exception:
                pass

        if last_logs:
            cls._trigger_background_logs_refresh(clean_id)
            start_idx = (page - 1) * limit
            return {
                "success": True,
                "logs": last_logs[start_idx : start_idx + limit],
                "page": page,
                "limit": limit,
                "totalLogs": len(last_logs),
                "source": "aws_api"
            }

        # Strictly non-blocking baseline: Return empty immediately (<1ms) and refresh in background
        cls._trigger_background_logs_refresh(clean_id)
        return {
            "success": True,
            "logs": [],
            "page": page,
            "limit": limit,
            "totalLogs": 0,
            "source": "aws_api"
        }

    @classmethod
    def _compute_activity_logs(cls, device_id: str, page: int = 1, limit: int = 20) -> dict:
        cls._refresh_7day_and_logs(device_id)
        clean_id = str(device_id).strip().lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()
        logs = _LAST_VALID_LOGS.get(clean_id, [])
        start_idx = (page - 1) * limit
        return {
            "success": True,
            "logs": logs[start_idx : start_idx + limit],
            "page": page,
            "limit": limit,
            "totalLogs": len(logs),
            "source": "aws_api"
        }

    @classmethod
    def start_telemetry_refresher_daemon(cls):
        """Starts background daemon that keeps active AWS telemetry perpetually fresh."""
        global _TELEMETRY_DAEMON_STARTED
        with _GLOBAL_LOCK:
            if _TELEMETRY_DAEMON_STARTED:
                return
            _TELEMETRY_DAEMON_STARTED = True

        def daemon_loop():
            # Initial wait for server boot & initial pre-warming
            time.sleep(8)
            logger.info("Continuous AWS telemetry refresher background daemon started.")
            while True:
                try:
                    time.sleep(30)
                    active_ids = [d for d in cls.get_known_device_ids() if cls.device_has_7day_data(d)]
                    today_str = datetime.now(IST).strftime("%d-%m-%Y")
                    for dev_id in active_ids:
                        try:
                            cls._compute_live_dashboard(dev_id, today_str)
                        except Exception:
                            pass
                        time.sleep(1.5)  # gentle pacing to avoid bursting CPU/network
                except Exception as e:
                    logger.warning(f"Error in telemetry refresher daemon: {e}")
                    time.sleep(30)

        t = threading.Thread(target=daemon_loop, daemon=True, name="AwsTelemetryRefresherDaemon")
        t.start()


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
                today_ist = datetime.now(IST).date()
                if dt.astimezone(IST).date() == today_ist:
                    is_today = True
            except Exception:
                pass

        mon_hours = h.get("monitoredHoursToday", 0.0) or 0.0
        rum_hours = h.get("ruminationHoursToday", 0.0) or 0.0
        lying_hours = h.get("lyingHoursToday", 0.0) or 0.0
        feed_hours = h.get("feedingHoursToday", 0.0) or 0.0
        move_hours = h.get("movingHoursToday", 0.0) or 0.0

        d_str = datetime.now(IST).strftime("%Y-%m-%d")
        today_s = _AWS_DAILY_SUMMARIES.get(dev_id, {}).get(d_str) or _AWS_DAILY_SUMMARIES.get(str(dev_id).replace("aws-", ""), {}).get(d_str)
        if today_s and (today_s.get("monitored_hours", 0.0) or 0.0) > mon_hours:
            mon_hours = today_s["monitored_hours"]
            rum_hours = today_s.get("rum_hours", rum_hours)
            lying_hours = today_s.get("lying_hours", lying_hours)
            feed_hours = today_s.get("feed_hours", feed_hours)
            move_hours = today_s.get("move_hours", move_hours)

        is_stale = dash.get("isStale", False) or (not is_today) or (mon_hours == 0.0)
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
            "ruminationHoursToday": 0.0 if is_stale else rum_hours,
            "lyingHoursToday": 0.0 if is_stale else lying_hours,
            "feedingHoursToday": 0.0 if is_stale else feed_hours,
            "movingHoursToday": 0.0 if is_stale else move_hours,
            "estrusProbability": 0 if is_stale else h.get("estrusProbabilityPercent", 0),
            "lastSeen": last_seen,
            "isStale": is_stale,
            "monitoredHoursToday": 0.0 if is_stale else mon_hours
        }

    @classmethod
    def device_has_7day_data(cls, dev_id: str) -> bool:
        """Checks if device has transmitted any data in the last 7 days relative to IST now."""
        if not dev_id:
            return False
        dev_key = str(dev_id).strip().lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()

        # 1. Check live dashboard cache
        cached_dash = _LAST_VALID_DASHBOARD.get(dev_key)
        if cached_dash and (cached_dash.get("healthStatus", {}).get("monitoredHoursToday", 0.0) or 0) > 0:
            return True

        # 2. Check 7-day daily summaries
        now_dt = datetime.now(IST)
        dates_7d = set((now_dt.date() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7))
        s_map = _AWS_DAILY_SUMMARIES.get(dev_key, {})
        for d_str in dates_7d:
            s = s_map.get(d_str, {})
            if (s.get("monitored_hours", 0.0) or 0) > 0 or (s.get("total_packets", 0) or 0) > 0:
                return True

        # 3. Check logs
        logs = _LAST_VALID_LOGS.get(dev_key, [])
        if isinstance(logs, list):
            for l in logs:
                st = l.get("startTime", "")[:10]
                if st in dates_7d:
                    return True

        # 4. Check PostgreSQL DailyCowSummary for any packets / monitored hours in the 7-day window
        try:
            from app.database import SessionLocal
            from app.models.datalogger import DailyCowSummary
            min_date = now_dt.date() - timedelta(days=6)
            with SessionLocal() as db:
                row = db.query(DailyCowSummary.id).filter(
                    DailyCowSummary.device_id == f"aws-{dev_key}",
                    DailyCowSummary.date >= min_date,
                    ((DailyCowSummary.monitored_hours > 0) | (DailyCowSummary.total_packets > 0))
                ).first()
                if row:
                    return True
        except Exception:
            pass

        # 5. For newly discovered device during active transmission, check today/yesterday packet cache
        now_str = now_dt.strftime("%d-%m-%Y")
        yest_str = (now_dt - timedelta(days=1)).strftime("%d-%m-%Y")
        for probe_d in [now_str, yest_str]:
            cache_k = f"raw_{dev_key}_{probe_d}_{probe_d}"
            cached_pkts = _AWS_CACHE.get(cache_k)
            if cached_pkts and len(cached_pkts.get("data", [])) > 0:
                return True

        return False

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
        Only includes devices that have transmitted data in the last 7 days.
        """
        if not device_ids:
            device_ids = cls.get_known_device_ids()

        items = []
        for dev_id in device_ids:
            dev_str = str(dev_id).strip()
            clean_id = dev_str.lower().replace("aws-", "").replace("aws ", "").replace("aws#", "").strip()

            # If device has no data in last 7 days, omit it
            if not cls.device_has_7day_data(clean_id):
                continue

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
                "lastSeen": None,
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
            device_ids = cls.get_known_device_ids()

        def worker():
            global _HERD_IS_REFRESHING, _HERD_ITEMS_CACHE
            try:
                cls.load_all_tag_metadata()
                items = []
                # Use max_workers=6 for fast parallel retrieval of all collar nodes
                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                    future_to_dev = {executor.submit(cls._fetch_single_herd_item, dev_id): dev_id for dev_id in device_ids}
                    for future in concurrent.futures.as_completed(future_to_dev):
                        try:
                            item = future.result()
                            if item and cls.device_has_7day_data(item.get("device_id")):
                                items.append(item)
                        except Exception as e:
                            dev_id = future_to_dev[future]
                            logger.warning(f"Error fetching AWS overview item for dev {dev_id}: {e}")

                if items:
                    items.sort(key=lambda x: _device_sort_key(x["device_id"]))
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
        Only returns devices that have transmitted data in the last 7 days.
        """
        global _HERD_ITEMS_CACHE
        now = time.time()

        if not device_ids:
            device_ids = cls.get_known_device_ids()

        # Opportunistic background auto-discovery trigger if interval elapsed
        if (now - _LAST_DISCOVERY_TIME) > (settings.AWS_AUTO_DISCOVERY_INTERVAL_MINUTES * 60):
            threading.Thread(target=cls.discover_devices, daemon=True, name="AwsAutoDiscoveryWorker").start()

        def filter_active(items_list):
            return [it for it in items_list if cls.device_has_7day_data(it.get("device_id"))]

        # If cache exists and is fresh, return filtered items
        if not force_refresh and _HERD_ITEMS_CACHE.get("expires_at", 0) > now and _HERD_ITEMS_CACHE.get("data"):
            return filter_active(_HERD_ITEMS_CACHE["data"])

        # If cache exists but is stale, trigger background refresh and return stale data immediately
        if _HERD_ITEMS_CACHE.get("data"):
            cls._trigger_background_herd_refresh(device_ids)
            return filter_active(_HERD_ITEMS_CACHE["data"])

        # Cold start: populate instant fallback items, trigger background refresh, and return immediately
        fallback_items = cls._build_fallback_herd_items(device_ids)
        _HERD_ITEMS_CACHE = {
            "expires_at": now + 30,
            "data": fallback_items
        }
        cls._trigger_background_herd_refresh(device_ids)
        return filter_active(fallback_items)


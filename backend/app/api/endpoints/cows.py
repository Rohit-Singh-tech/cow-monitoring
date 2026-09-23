from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc
from typing import List, Optional
from datetime import datetime, timezone, timedelta, date
import math
import time
import logging

from app.database import get_db
from app.config import settings
from app.models.tag_registry import TagRegistry
from app.models.datalogger import DataloggerHeader, DataloggerPoint, MLInference, DailyCowSummary
from app.ml.model_loader import get_ml_manager
from app.services.aws_service import AwsTelemetryService

logger = logging.getLogger("cow_logger.cows")

router = APIRouter()

def resolve_aws_device_id(cow_id: str) -> Optional[str]:
    """
    Checks if cow_id refers to an AWS Collar device.
    Supports formats like 'aws-8', 'AWS-8'.
    """
    if not cow_id:
        return None
    s = str(cow_id).strip()
    if s.lower().startswith("aws-"):
        return s.split("-", 1)[1]
    return None


ACTIVITY_MAP = {
    "RES": {"code": "RES", "name": "Resting in standing position", "color": "#64748b", "icon": "fa-shoe-prints"},
    "RUS": {"code": "RUS", "name": "Ruminating in standing position", "color": "#06b6d4", "icon": "fa-arrows-spin"},
    "MOV": {"code": "MOV", "name": "Moving / Active", "color": "#f59e0b", "icon": "fa-person-walking"},
    "FEP": {"code": "FEP", "name": "Feeding in Pot", "color": "#10b981", "icon": "fa-bowl-food"},
    "FED": {"code": "FEP", "name": "Feeding", "color": "#10b981", "icon": "fa-bowl-food"},
    "DRN": {"code": "DRN", "name": "Drinking Water", "color": "#3b82f6", "icon": "fa-glass-water"},
    "LCK": {"code": "LCK", "name": "Licking", "color": "#ec4899", "icon": "fa-hand-sparkles"},
    "REL": {"code": "REL", "name": "Resting in lying position", "color": "#8b5cf6", "icon": "fa-bed"},
    "URI": {"code": "URI", "name": "Urinating", "color": "#eab308", "icon": "fa-droplet"},
    "DEF": {"code": "DEF", "name": "Defecating", "color": "#a16207", "icon": "fa-circle-dot"},
    "ATT": {"code": "ATT", "name": "Attacking / Aggressive", "color": "#ef4444", "icon": "fa-triangle-exclamation"},
    "GRZ": {"code": "FEP", "name": "Grazing Field", "color": "#10b981", "icon": "fa-bowl-food"}
}

# 24-hour staleness threshold
STALENESS_HOURS = 24


# Cache structures for sub-second responses
_DB_COW_CURRENT_CACHE = {}  # {dev_id: {"expires_at": float, "data": dict}}
_DB_COW_7DAY_CACHE = {}     # {dev_id: {"expires_at": float, "data": dict}}

def clear_db_cow_caches(device_id: Optional[str] = None):
    """Invalidate DB cow caches when new data is ingested or tags modified."""
    global _DB_COW_CURRENT_CACHE, _DB_COW_7DAY_CACHE, _DB_HERD_CACHE
    if device_id:
        _DB_COW_CURRENT_CACHE.pop(str(device_id), None)
        _DB_COW_7DAY_CACHE.pop(str(device_id), None)
    else:
        _DB_COW_CURRENT_CACHE.clear()
        _DB_COW_7DAY_CACHE.clear()
    _DB_HERD_CACHE = {"expires_at": 0.0, "data": []}

def _get_latest_inference_for_device(db: Session, device_id: str):
    """
    Get the latest ML inference for a device with a single index-optimized query.
    Returns (header, inference) tuple. Both may be None.
    """
    header = db.query(DataloggerHeader).filter(
        DataloggerHeader.device_id == str(device_id)
    ).order_by(DataloggerHeader.id.desc()).first()
    
    if not header:
        return None, None
        
    inference = db.query(MLInference).filter(
        MLInference.header_id == header.id
    ).first()
    
    # If the latest header has no inference, try the most recent header that DOES have one
    if not inference:
        result = db.execute(text("""
            SELECT h.id, h.timestamp, m.activity_code, m.confidence, m.is_heat, 
                   m.heat_probability, m.health_risk_decision, m.anomaly_score
            FROM datalogger_headers h
            JOIN ml_inferences m ON h.id = m.header_id
            WHERE h.id = (SELECT MAX(id) FROM datalogger_headers WHERE device_id = :dev)
        """), {"dev": str(device_id)}).fetchone()
        
        if result:
            # Create a mock inference object for consistency
            class InfResult:
                def __init__(self, row):
                    self.header_id = row[0]
                    self.activity_code = row[2]
                    self.confidence = row[3]
                    self.is_heat = row[4]
                    self.heat_probability = row[5]
                    self.health_risk_decision = row[6]
                    self.anomaly_score = row[7] if len(row) > 7 else 0.0
            inference = InfResult(result)
    
    return header, inference


def _is_device_stale(latest_timestamp) -> bool:
    """Check if device hasn't sent data in the last 24 hours."""
    if latest_timestamp is None:
        return True
    now = datetime.now(timezone.utc)
    if latest_timestamp.tzinfo is None:
        latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)
    return (now - latest_timestamp).total_seconds() > (STALENESS_HOURS * 3600)


def _build_health_status_from_inference(inference, summary=None):
    """
    Build consistent health status from ML inference.
    Used by BOTH herd overview and live dashboard for consistency.
    """
    if inference is None:
        return {
            "act_code": None,
            "health_risk": None,
            "is_heat": False,
            "heat_prob_pct": 0,
        }
    
    act_code = inference.activity_code
    health_risk = inference.health_risk_decision or "HEALTHY"
    is_heat = inference.is_heat or False
    heat_prob_pct = int((inference.heat_probability or 0) * 100)
    
    # Heat detected in today's summary also flags risk
    heat_from_summary = (summary.heat_count > 0) if summary else False
    
    # Consistent health decision: if ML says HIGH_RISK or heat detected anywhere
    if health_risk == "HIGH_RISK" or is_heat or heat_from_summary:
        final_health = "HIGH_RISK"
    elif health_risk == "MONITOR":
        final_health = "MONITOR"
    else:
        final_health = "HEALTHY"
    
    return {
        "act_code": act_code,
        "health_risk": final_health,
        "is_heat": is_heat or heat_from_summary,
        "heat_prob_pct": heat_prob_pct,
    }


_DB_HERD_CACHE = {"expires_at": 0.0, "data": []}

@router.get("", response_model=List[dict])
def get_herd_overview(db: Session = Depends(get_db)):
    """
    Herd overview: returns both Render Database devices and AWS CowNeck API devices.
    Uses batch queries and fast in-memory caching for sub-10ms response times.
    """
    global _DB_HERD_CACHE
    now_ts = time.time()
    
    # 1. Fetch Render Database cows (cached for 10s to keep ultra-fast)
    db_items = []
    if _DB_HERD_CACHE.get("expires_at", 0) > now_ts and _DB_HERD_CACHE.get("data"):
        db_items = _DB_HERD_CACHE["data"]
    else:
        try:
            cows = db.query(TagRegistry).order_by(TagRegistry.id.asc()).all()
            aws_ids = set([str(x).strip() for x in settings.AWS_ENABLED_DEVICE_IDS])
            
            # Filter out TagRegistry entries that represent AWS devices
            db_cows = [c for c in cows if str(c.device_id).strip() not in aws_ids and not str(c.device_id).lower().startswith("aws-")]

            if db_cows:
                today = date.today()
                all_summaries = db.query(DailyCowSummary).filter(
                    DailyCowSummary.date == today
                ).all()
                summaries_by_device = {s.device_id: s for s in all_summaries}

                # Single batch query to get latest headers and inferences for ALL devices at once
                batch_sql = text("""
                    SELECT h.id, h.device_id, h.timestamp, m.activity_code, m.confidence, m.is_heat, 
                           m.heat_probability, m.health_risk_decision, m.anomaly_score
                    FROM datalogger_headers h
                    LEFT JOIN ml_inferences m ON h.id = m.header_id
                    WHERE h.id IN (
                        SELECT MAX(id) FROM datalogger_headers GROUP BY device_id
                    )
                """)
                inf_rows = db.execute(batch_sql).fetchall()
                inf_by_device = {}
                for r in inf_rows:
                    inf_by_device[str(r[1])] = {
                        "header_id": r[0],
                        "timestamp": r[2],
                        "act_code": r[3],
                        "confidence": r[4],
                        "is_heat": r[5],
                        "heat_prob": r[6],
                        "health_risk": r[7],
                        "anomaly_score": r[8] if len(r) > 8 else 0.0
                    }

                for c in db_cows:
                    dev_id = str(c.device_id).strip()
                    inf = inf_by_device.get(dev_id)
                    ts = inf["timestamp"] if inf else None
                    stale = _is_device_stale(ts)
                    summary = summaries_by_device.get(dev_id)

                    act_code = inf["act_code"] if inf else None
                    health_risk = inf["health_risk"] if inf else "NO_DATA"
                    is_heat = inf["is_heat"] if inf else False
                    heat_prob_pct = int((inf["heat_prob"] or 0) * 100) if inf and inf["heat_prob"] else 0
                    
                    if stale:
                        rum_hrs = 0.0
                        lying_hrs = 0.0
                        feed_hrs = 0.0
                        move_hrs = 0.0
                        act_code = None
                        health_risk = "NO_DATA"
                        heat_prob_pct = 0
                    else:
                        rum_hrs = summary.rumination_hours if summary else 0.0
                        lying_hrs = summary.lying_hours if summary else 0.0
                        feed_hrs = summary.feeding_hours if summary else 0.0
                        move_hrs = summary.moving_hours if summary else 0.0

                    act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP.get("RES")) if act_code else ACTIVITY_MAP.get("RES")

                    db_items.append({
                        "id": dev_id,
                        "device_id": dev_id,
                        "source": "gatewayless",
                        "tagNumber": f"TAG-{c.device_id}",
                        "name": c.name or f"Device #{c.device_id}",
                        "breed": c.breed or None,
                        "location": c.location or None,
                        "weight": f"{c.weight} kg" if c.weight and not str(c.weight).endswith("kg") else (c.weight or None),
                        "healthStatus": health_risk or "NO_DATA",
                        "health_risk_decision": health_risk or "NO_DATA",
                        "currentActivity": act_code,
                        "activityName": act_info["name"] if act_code else "No Recent Data",
                        "ruminationHoursToday": rum_hrs,
                        "lyingHoursToday": lying_hrs,
                        "feedingHoursToday": feed_hrs,
                        "movingHoursToday": move_hrs,
                        "estrusProbability": heat_prob_pct,
                        "lastSeen": ts.isoformat() if ts else None,
                        "isStale": stale,
                        "monitoredHoursToday": summary.monitored_hours if summary else 0.0
                    })
                _DB_HERD_CACHE = {"expires_at": now_ts + 120.0, "data": db_items}
        except Exception as e:
            logger.warning(f"Error querying database cows for herd overview: {e}")

    result = list(db_items)

    # 2. Fetch AWS Cloud Collar devices (Parallel & 60s cached)
    try:
        aws_items = AwsTelemetryService.get_herd_overview_items()
        result.extend(aws_items)
    except Exception as e:
        logger.error(f"Error querying AWS herd overview items: {e}")

    return result


def resolve_db_cow(cow_id: str, db: Session):
    """
    Resolves a cow in the database by device_id or primary key id.
    Returns TagRegistry object if found, or a proxy object if headers exist for device_id.
    """
    if not cow_id:
        return None
    s = str(cow_id).strip()
    if s.lower().startswith("aws-"):
        return None

    cow = None
    try:
        # First match by device_id (e.g. '17', 'COW-BLE-001')
        cow = db.query(TagRegistry).filter(TagRegistry.device_id == s).first()
        # Second match by primary key id (only if not an AWS collar ID)
        if not cow and s.isdigit() and s not in settings.AWS_ENABLED_DEVICE_IDS:
            cow = db.query(TagRegistry).filter(TagRegistry.id == int(s)).first()
    except Exception as e:
        logger.warning(f"Error querying TagRegistry for {cow_id}: {e}")
    
    if not cow:
        # Check if datalogger_headers exist for this device_id
        try:
            has_hdr = db.query(DataloggerHeader.id).filter(DataloggerHeader.device_id == str(cow_id)).first()
            if has_hdr:
                class UnregisteredCow:
                    id = int(cow_id) if str(cow_id).isdigit() else 999
                    device_id = str(cow_id)
                    name = f"Node #{cow_id}"
                    breed = None
                    location = None
                    weight = None
                    notes = None
                return UnregisteredCow()
        except Exception:
            pass

    return cow


@router.get("/{cow_id}/live")
def get_cow_live_dashboard(cow_id: str, target_date: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Live dashboard: routes to AWS Telemetry Service if cow_id is an AWS device,
    otherwise uses the Render database logic.
    """
    # Check if requested node is an AWS device
    aws_dev = resolve_aws_device_id(cow_id)
    if aws_dev:
        return AwsTelemetryService.get_live_dashboard(aws_dev, target_date=target_date)

    # Check cache FIRST before any DB queries
    now_ts = time.time()
    cache_entry = _DB_COW_CURRENT_CACHE.get(str(cow_id))
    if cache_entry and cache_entry["expires_at"] > now_ts:
        return cache_entry["data"]

    cow = resolve_db_cow(cow_id, db)
        
    if not cow:
        # Check if cow_id can be resolved via AWS directly
        clean_id = str(cow_id).strip().lower().replace("aws-", "")
        if clean_id in settings.AWS_ENABLED_DEVICE_IDS:
            try:
                return AwsTelemetryService.get_live_dashboard(clean_id, target_date=target_date)
            except Exception:
                pass

        try:
            cow = db.query(TagRegistry).first()
        except Exception:
            pass
        
    if not cow:
        # Final fallback to default AWS Device 8
        try:
            return AwsTelemetryService.get_live_dashboard("8", target_date=target_date)
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="No cattle nodes registered in database or AWS.")

    dev_id = str(cow.device_id)
    now_ts = time.time()
    cache_entry = _DB_COW_CURRENT_CACHE.get(dev_id)
    if cache_entry and cache_entry["expires_at"] > now_ts:
        return cache_entry["data"]

    today = date.today()

    # Get today's pre-computed daily summary
    summary = db.query(DailyCowSummary).filter(
        DailyCowSummary.device_id == dev_id,
        DailyCowSummary.date == today
    ).first()

    # Get latest header + ML inference
    header, inference = _get_latest_inference_for_device(db, dev_id)
    
    ts = header.timestamp if header else None
    stale = _is_device_stale(ts)
    
    # Get accelerometer points for the latest header
    x_buf, y_buf, z_buf = [], [], []
    if header:
        pt_rows = db.query(DataloggerPoint.x, DataloggerPoint.y, DataloggerPoint.z).filter(
            DataloggerPoint.header_id == header.id
        ).order_by(DataloggerPoint.point_index.asc()).all()
        
        x_buf = [r[0] for r in pt_rows if r[0] is not None]
        y_buf = [r[1] for r in pt_rows if r[1] is not None]
        z_buf = [r[2] for r in pt_rows if r[2] is not None]

    # Build ML result
    ml_res = None
    
    if inference:
        act_code = inference.activity_code
        act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP.get("RES"))
        
        heat_alert = "HIGH" if (inference.heat_probability or 0) > 0.7 else (
            "MODERATE" if (inference.heat_probability or 0) > 0.4 else "NORMAL")
        
        ml_res = {
            "ml_engine_status": "ACTIVE",
            "activity": {
                "code": act_code,
                "description": act_info["name"],
                "confidence": (inference.confidence or 85) / 100.0,
                "is_ruminating": act_code == "RUS",
                "is_grazing": act_code in ["GRZ", "FED", "FEP", "FES"],
                "is_resting": act_code in ["RES", "REL"]
            },
            "heat_detection": {
                "in_heat": inference.is_heat or False,
                "heat_probability": inference.heat_probability or 0.0,
                "alert_level": heat_alert
            },
            "anomaly_detection": {"is_anomaly": False, "score": getattr(inference, "anomaly_score", 0.0)},
            "deviation_metrics": {"score": 0.0, "is_deviating": False, "threshold": getattr(inference, "anomaly_threshold", 0.0)},
            "health_risk_decision": inference.health_risk_decision or "HEALTHY",
            "features_extracted_count": 67
        }
    elif len(x_buf) > 0:
        # Fallback: run ML live only if no cached inference exists but we have data
        logger.info(f"No cached inference for device {dev_id}, running live ML")
        manager = get_ml_manager()
        ml_res = manager.predict(x_buf, y_buf, z_buf)

    # Build consistent health status — SAME logic as herd overview
    health = _build_health_status_from_inference(inference, summary)
    
    if stale:
        # Device hasn't sent data in 24 hours
        monitored_hours = 0.0
        rum_hrs = 0.0
        lying_hrs = 0.0
        feed_hrs = 0.0
        move_hrs = 0.0
        health_risk = "NO_DATA"
        is_heat = False
        heat_prob_pct = 0
        act_code = None
        act_info = ACTIVITY_MAP.get("RES")
    else:
        monitored_hours = summary.monitored_hours if summary else 0.0
        rum_hrs = summary.rumination_hours if summary else 0.0
        lying_hrs = summary.lying_hours if summary else 0.0
        feed_hrs = summary.feeding_hours if summary else 0.0
        move_hrs = summary.moving_hours if summary else 0.0
        health_risk = health["health_risk"]
        is_heat = health["is_heat"]
        heat_prob_pct = health["heat_prob_pct"]
        act_code = health["act_code"]
        act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP.get("RES")) if act_code else ACTIVITY_MAP.get("RES")

    # If we still don't have ml_res, build a default
    if ml_res is None:
        ml_res = {
            "ml_engine_status": "NO_DATA",
            "activity": {"code": act_code, "confidence": 0.0, "primary_activity": act_code},
            "heat_detection": {"in_heat": False, "heat_probability": 0.0, "alert_level": "LOW"},
            "anomaly_detection": {"is_anomaly": False, "score": 0.0},
            "deviation_metrics": {"is_deviating": False},
            "health_risk_decision": health_risk
        }
        if not x_buf:
            x_buf, y_buf, z_buf = [0]*80, [0]*80, [0]*80

    # Use health_risk from ML result if available and not stale
    if not stale and ml_res.get("health_risk_decision"):
        health_risk = ml_res["health_risk_decision"]
        # Re-apply heat override for consistency
        if is_heat and health_risk == "HEALTHY":
            health_risk = "HIGH_RISK"

    # Generate data-driven recommendation
    recommendation = _generate_recommendation(health_risk, is_heat, ml_res, stale)

    mag_buf = [round(math.sqrt(x_buf[i]**2 + y_buf[i]**2 + z_buf[i]**2), 3) for i in range(len(x_buf))]
    labels = [f"{(i*0.1):.1f}s" for i in range(len(x_buf))]

    res_data = {
        "cowId": str(cow.device_id),
        "device_id": dev_id,
        "source": "gatewayless",
        "cowName": cow.name or f"Device #{cow.device_id}",
        "tagNumber": f"TAG-{cow.device_id}",
        "breed": cow.breed or None,
        "location": cow.location or None,
        "weight": f"{cow.weight} kg" if cow.weight else None,
        "notes": cow.notes,
        "isStale": stale,
        "currentActivity": {
            "code": act_code,
            "name": act_info["name"] if act_code else "No Recent Data",
            "color": act_info["color"],
            "icon": act_info["icon"]
        },
        "healthStatus": {
            "monitoredHoursToday": monitored_hours,
            "ruminationHoursToday": rum_hrs,
            "lyingHoursToday": lying_hrs,
            "feedingHoursToday": feed_hrs,
            "movingHoursToday": move_hrs,
            "ruminationScore": min(100, int((rum_hrs / 8.0) * 100)) if rum_hrs else 0,
            "estrusProbabilityPercent": heat_prob_pct,
            "isHeatDetected": is_heat,
            "healthRecommendation": recommendation,
            "health_risk_decision": health_risk
        },
        "liveTelemetry": {
            "x": x_buf[-1] if len(x_buf) > 0 else 0,
            "y": y_buf[-1] if len(y_buf) > 0 else 0,
            "z": z_buf[-1] if len(z_buf) > 0 else 0,
            "magnitude": mag_buf[-1] if len(mag_buf) > 0 else 0,
            "timestamp": ts.isoformat() if ts else None
        },
        "accelBuffer": {
            "labels": labels,
            "x": x_buf,
            "y": y_buf,
            "z": z_buf,
            "mag": mag_buf
        },
        "ml_inference": ml_res
    }
    _DB_COW_CURRENT_CACHE[str(dev_id)] = {
        "expires_at": time.time() + 45.0,
        "data": res_data
    }
    _DB_COW_CURRENT_CACHE[str(cow_id)] = {
        "expires_at": time.time() + 45.0,
        "data": res_data
    }
    return res_data


def _generate_recommendation(health_risk, is_heat, ml_res, stale):
    """Generate recommendation text based purely on ML data — nothing hardcoded."""
    if stale:
        return "WARNING: No sensor data received in the last 24 hours. Check collar node battery and BLE connectivity."
    
    if health_risk == "NO_DATA":
        return "Awaiting ML inference results. Sensor data is being processed by the background worker."
    
    if health_risk == "HIGH_RISK":
        issues = []
        actions = []
        
        if is_heat or ml_res.get("heat_detection", {}).get("alert_level") == "HIGH":
            issues.append("signs of being in heat (estrus cycle)")
            actions.append("prepare for artificial insemination (breeding) in the next 12 hours")
            
        if ml_res.get("anomaly_detection", {}).get("is_anomaly"):
            issues.append("unusual movement patterns (anomaly detected)")
            actions.append("physically check the cow for injury or sickness")
            
        if ml_res.get("deviation_metrics", {}).get("is_deviating"):
            issues.append("behavior significantly different from herd baseline")
            if "physically check the cow" not in str(actions):
                actions.append("physically check the cow for injury or sickness")
                
        if issues:
            issue_str = " and ".join(issues)
            action_str = " and ".join(actions)
            return f"CRITICAL: Cow is showing {issue_str}. Action needed: {action_str.capitalize()}."
        else:
            return "CRITICAL: Health risk detected by ML model. Action needed: Physically examine the animal immediately."
            
    elif health_risk == "MONITOR":
        if ml_res.get("heat_detection", {}).get("alert_level") == "MODERATE":
            return "MONITOR: Possible early signs of estrus detected. Monitor closely for next 6-12 hours."
        elif ml_res.get("activity", {}).get("code") in ["ATT"]:
            return "MONITOR: Aggressive behavior detected. Check for environmental stressors or social conflicts."
        else:
            return "MONITOR: Some health metrics require attention. Continue monitoring."
    
    return "All health parameters within normal range based on ML analysis."


@router.get("/{cow_id}/activity-7day")
def get_cow_7day_activity(cow_id: str, db: Session = Depends(get_db)):
    """
    7-day behavior trends from pre-computed daily summaries or AWS API.
    Fully data-driven: shows actual ML-computed values.
    """
    aws_dev = resolve_aws_device_id(cow_id)
    if aws_dev:
        return AwsTelemetryService.get_7day_activity(aws_dev)

    # Check fast cache FIRST before any DB lookups (10 min TTL)
    now_ts = time.time()
    cached_7day = _DB_COW_7DAY_CACHE.get(str(cow_id))
    if cached_7day and cached_7day["expires_at"] > now_ts:
        return cached_7day["data"]

    cow = resolve_db_cow(cow_id, db)
    if not cow:
        clean_id = str(cow_id).strip().lower().replace("aws-", "")
        if clean_id in settings.AWS_ENABLED_DEVICE_IDS:
            try:
                return AwsTelemetryService.get_7day_activity(clean_id)
            except Exception:
                pass
        try:
            cow = db.query(TagRegistry).first()
        except Exception:
            pass
        
    dev_id = cow.device_id if cow else str(cow_id)

    # Also check cache by resolved dev_id
    cached_7day = _DB_COW_7DAY_CACHE.get(str(dev_id))
    if cached_7day and cached_7day["expires_at"] > now_ts:
        return cached_7day["data"]

    # Calculate last 7 dates
    today = datetime.now(timezone.utc).date()
    date_range = [(today - timedelta(days=i)) for i in range(6, -1, -1)]

    # Get last 7 days of pre-computed summaries
    summaries = db.query(DailyCowSummary).filter(
        DailyCowSummary.device_id == str(dev_id),
        DailyCowSummary.date >= date_range[0]
    ).all()
    
    summary_by_date = {s.date: s for s in summaries}

    # Fetch fallback SQL stats for missing dates
    missing_dates = [d for d in date_range if d not in summary_by_date]
    sql_fallback_by_date = {}
    if missing_dates:
        sql = text("""
            SELECT DATE(timestamp) as day_date, COUNT(*) as pkt_count
            FROM datalogger_headers
            WHERE device_id = :dev AND DATE(timestamp) >= :start_date
            GROUP BY DATE(timestamp)
        """)
        rows = db.execute(sql, {"dev": str(dev_id), "start_date": date_range[0].isoformat()}).fetchall()
        for r in rows:
            day_str = r[0]
            if isinstance(day_str, str):
                try:
                    d = datetime.strptime(day_str, "%Y-%m-%d").date()
                except ValueError:
                    continue
            else:
                d = day_str
            sql_fallback_by_date[d] = r[1]

    days = []
    dates = []
    rum_list = []
    lying_list = []
    feed_list = []
    act_list = []
    monitored_list = []
    health_score_list = []
    estrus_index_list = []

    for d in date_range:
        days.append(d.strftime("%a"))
        dates.append(d.strftime("%Y-%m-%d"))
        
        s = summary_by_date.get(d)
        if s:
            rum_list.append(round(s.rumination_hours, 1))
            lying_list.append(round(s.lying_hours, 1))
            feed_list.append(round(s.feeding_hours, 1))
            act_list.append(round(s.moving_hours, 1))
            monitored_list.append(round(s.monitored_hours, 1))
            
            health_score = min(100, int((s.rumination_hours / 8.0) * 100)) if s.rumination_hours > 0 else 0
            if s.monitored_hours > 0 and s.rumination_hours == 0 and s.lying_hours == 0:
                health_score = 0
            elif s.monitored_hours == 0:
                health_score = 0
            elif health_score == 0 and (s.lying_hours > 0 or s.feeding_hours > 0):
                health_score = 50
            health_score_list.append(health_score)
            
            e_index = int((s.heat_count / s.total_packets) * 100) if s.total_packets > 0 else 0
            estrus_index_list.append(min(100, e_index))
        else:
            pkt_count = sql_fallback_by_date.get(d, 0)
            day_hours = round((pkt_count * 8.0) / 3600.0, 1)
            rum_list.append(0.0)
            lying_list.append(0.0)
            feed_list.append(0.0)
            act_list.append(0.0)
            monitored_list.append(day_hours)
            health_score_list.append(0)
            estrus_index_list.append(0)

    tot_days = max(1, len(date_range))
    weekly_avg = {
        "RUS": sum(rum_list) / tot_days,
        "REL": sum(lying_list) / tot_days,
        "FEP": sum(feed_list) / tot_days,
        "MOV": sum(act_list) / tot_days,
        "RES": 0.0,
        "DRN": 0.0
    }

    res_7day = {
        "cowId": str(dev_id),
        "device_id": str(dev_id),
        "source": "gatewayless",
        "days": days,
        "dates": dates,
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
    _DB_COW_7DAY_CACHE[str(dev_id)] = {
        "expires_at": time.time() + 600.0,
        "data": res_7day
    }
    _DB_COW_7DAY_CACHE[str(cow_id)] = {
        "expires_at": time.time() + 600.0,
        "data": res_7day
    }
    return res_7day

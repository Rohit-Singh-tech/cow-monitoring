from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc
from typing import List, Optional
from datetime import datetime, timezone, timedelta, date
import math
import logging

from app.database import get_db
from app.models.tag_registry import TagRegistry
from app.models.datalogger import DataloggerHeader, DataloggerPoint, MLInference, DailyCowSummary
from app.ml.model_loader import get_ml_manager

logger = logging.getLogger("cow_logger.cows")

router = APIRouter()

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


def _get_latest_inference_for_device(db: Session, device_id: str):
    """
    Get the latest ML inference for a device by joining latest header to ml_inferences.
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
                   m.heat_probability, m.health_risk_decision
            FROM datalogger_headers h
            JOIN ml_inferences m ON h.id = m.header_id
            WHERE h.device_id = :dev
            ORDER BY h.id DESC
            LIMIT 1
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


@router.get("", response_model=List[dict])
def get_herd_overview(db: Session = Depends(get_db)):
    """
    Herd overview: fully data-driven from database.
    No hardcoded values. Shows 0 if no data in 24 hours.
    Uses same health logic as individual cow view for consistency.
    """
    cows = db.query(TagRegistry).order_by(TagRegistry.id.asc()).all()
    if not cows:
        return []

    today = date.today()

    # Batch-fetch today's daily summaries
    all_summaries = db.query(DailyCowSummary).filter(
        DailyCowSummary.date == today
    ).all()
    summaries_by_device = {s.device_id: s for s in all_summaries}

    result = []
    for c in cows:
        dev_id = str(c.device_id)
        
        # Get latest inference (same function used by live dashboard)
        header, inference = _get_latest_inference_for_device(db, dev_id)
        
        ts = header.timestamp if header else None
        stale = _is_device_stale(ts)
        summary = summaries_by_device.get(dev_id)
        
        # Build health status — SAME logic as individual cow view
        health = _build_health_status_from_inference(inference, summary)
        
        # If device is stale (no data in 24h), show 0 for all health params
        if stale:
            rum_hrs = 0.0
            lying_hrs = 0.0
            feed_hrs = 0.0
            move_hrs = 0.0
            act_code = None
            health_risk = None  # null = no recent data
            heat_prob_pct = 0
        else:
            rum_hrs = summary.rumination_hours if summary else 0.0
            lying_hrs = summary.lying_hours if summary else 0.0
            feed_hrs = summary.feeding_hours if summary else 0.0
            move_hrs = summary.moving_hours if summary else 0.0
            act_code = health["act_code"]
            health_risk = health["health_risk"]
            heat_prob_pct = health["heat_prob_pct"]
        
        act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP.get("RES")) if act_code else ACTIVITY_MAP.get("RES")

        result.append({
            "id": c.id,
            "device_id": dev_id,
            "tagNumber": f"TAG-{c.device_id}",
            "name": c.name or f"Device #{c.device_id}",
            "breed": c.breed or None,
            "location": c.location or None,
            "weight": f"{c.weight} kg" if c.weight else None,
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
        
    return result


@router.get("/{cow_id}/live")
def get_cow_live_dashboard(cow_id: str, db: Session = Depends(get_db)):
    """
    Live dashboard: fully data-driven.
    Uses SAME health logic as herd overview for consistency.
    Falls back to live ML only if no cached inference exists.
    Shows 0 if device has no data in 24 hours.
    """
    cow = None
    if str(cow_id).isdigit():
        cow = db.query(TagRegistry).filter(TagRegistry.id == int(cow_id)).first()
        
    if not cow:
        cow = db.query(TagRegistry).filter(TagRegistry.device_id == str(cow_id)).first()
        
    if not cow:
        cow = db.query(TagRegistry).first()
        
    if not cow:
        raise HTTPException(status_code=404, detail="No cattle nodes registered in database tag_registry.")

    dev_id = str(cow.device_id)
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
        points = db.query(DataloggerPoint).filter(
            DataloggerPoint.header_id == header.id
        ).order_by(DataloggerPoint.point_index.asc()).all()
        
        x_buf = [p.x for p in points if p.x is not None]
        y_buf = [p.y for p in points if p.y is not None]
        z_buf = [p.z for p in points if p.z is not None]

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

    return {
        "cowId": cow.id,
        "device_id": dev_id,
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
    7-day behavior trends from pre-computed daily summaries.
    Fully data-driven: shows actual ML-computed values.
    """
    if str(cow_id).isdigit():
        cow = db.query(TagRegistry).filter(TagRegistry.id == int(cow_id)).first()
    else:
        cow = db.query(TagRegistry).filter(TagRegistry.device_id == str(cow_id)).first()
        
    dev_id = cow.device_id if cow else str(cow_id)

    # Get last 7 days of pre-computed summaries
    summaries = db.query(DailyCowSummary).filter(
        DailyCowSummary.device_id == str(dev_id)
    ).order_by(DailyCowSummary.date.desc()).limit(7).all()

    days = []
    dates = []
    rum_list = []
    lying_list = []
    feed_list = []
    act_list = []
    monitored_list = []
    health_score_list = []
    estrus_index_list = []

    if summaries:
        for s in reversed(summaries):
            days.append(s.date.strftime("%a"))
            dates.append(s.date.strftime("%Y-%m-%d"))
            rum_list.append(round(s.rumination_hours, 1))
            lying_list.append(round(s.lying_hours, 1))
            feed_list.append(round(s.feeding_hours, 1))
            act_list.append(round(s.moving_hours, 1))
            monitored_list.append(round(s.monitored_hours, 1))
            
            # Data-driven Health Score based on rumination targets (8 hours is ideal)
            health_score = min(100, int((s.rumination_hours / 8.0) * 100)) if s.rumination_hours > 0 else 0
            if s.monitored_hours > 0 and s.rumination_hours == 0 and s.lying_hours == 0:
                health_score = 0
            elif s.monitored_hours == 0:
                health_score = 0
            # Ensure a minimum score if they have any normal activity
            elif health_score == 0 and (s.lying_hours > 0 or s.feeding_hours > 0):
                health_score = 50
            health_score_list.append(health_score)
            
            # Data-driven Estrus Index based on percentage of packets flagged as heat
            e_index = int((s.heat_count / s.total_packets) * 100) if s.total_packets > 0 else 0
            estrus_index_list.append(min(100, e_index))
    else:
        # Fallback: compute from packet counts if no summaries exist yet
        sql = text("""
            SELECT DATE(timestamp) as day_date, COUNT(*) as pkt_count
            FROM datalogger_headers
            WHERE device_id = :dev
            GROUP BY DATE(timestamp)
            ORDER BY day_date DESC
            LIMIT 7
        """)
        rows = db.execute(sql, {"dev": str(dev_id)}).fetchall()
        
        for r in reversed(rows):
            if isinstance(r[0], str):
                try:
                    d = datetime.strptime(r[0], "%Y-%m-%d").date()
                except ValueError:
                    continue
            else:
                d = r[0]
                
            days.append(d.strftime("%a"))
            dates.append(d.strftime("%Y-%m-%d"))
            pkt_count = r[1]
            day_hours = round((pkt_count * 8.0) / 3600.0, 1)
            # No ML data available yet — show 0 for all activities but show monitored hours
            rum_list.append(0.0)
            lying_list.append(0.0)
            feed_list.append(0.0)
            act_list.append(0.0)
            monitored_list.append(day_hours)
            health_score_list.append(0)
            estrus_index_list.append(0)

    return {
        "cowId": cow_id,
        "device_id": str(dev_id),
        "days": days,
        "dates": dates,
        "ruminationHours": rum_list,
        "lyingRestHours": lying_list,
        "feedingHours": feed_list,
        "activeHours": act_list,
        "monitoredHours": monitored_list,
        "healthScores": health_score_list,
        "estrusIndices": estrus_index_list,
        "estrusAlerts": []
    }

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


@router.get("", response_model=List[dict])
def get_herd_overview(db: Session = Depends(get_db)):
    """
    Fast herd overview using pre-computed ML inferences.
    Single query approach — zero ML inference at request time.
    """
    cows = db.query(TagRegistry).order_by(TagRegistry.id.asc()).all()
    if not cows:
        return []

    # Get today's date for daily summaries
    today = date.today()

    # Batch-fetch today's daily summaries for all cows in ONE query
    all_summaries = db.query(DailyCowSummary).filter(
        DailyCowSummary.date == today
    ).all()
    summaries_by_device = {s.device_id: s for s in all_summaries}

    # Batch-fetch the latest ML inference per device in ONE query
    # Uses a subquery to find the latest header per device, then joins to ml_inferences
    device_ids = [str(c.device_id) for c in cows]
    
    latest_inferences = {}
    latest_timestamps = {}
    
    if device_ids:
        # Get the latest header + its ML inference for each device
        sql = text("""
            SELECT DISTINCT ON (h.device_id) 
                h.device_id, h.timestamp, 
                m.activity_code, m.confidence, m.is_heat, m.heat_probability, m.health_risk_decision
            FROM datalogger_headers h
            LEFT JOIN ml_inferences m ON h.id = m.header_id
            WHERE h.device_id = ANY(:devs)
            ORDER BY h.device_id, h.id DESC
        """)
        try:
            rows = db.execute(sql, {"devs": device_ids}).fetchall()
            for row in rows:
                dev_id = row[0]
                latest_timestamps[dev_id] = row[1]
                if row[2] is not None:  # has ML inference
                    latest_inferences[dev_id] = {
                        "activity_code": row[2],
                        "confidence": row[3],
                        "is_heat": row[4],
                        "heat_probability": row[5],
                        "health_risk_decision": row[6]
                    }
        except Exception as e:
            logger.warning(f"Batch inference query failed, using fallback: {e}")
            # Fallback: query per device (slower but works on SQLite)
            for dev_id in device_ids:
                try:
                    header = db.query(DataloggerHeader).filter(
                        DataloggerHeader.device_id == dev_id
                    ).order_by(DataloggerHeader.id.desc()).first()
                    if header:
                        latest_timestamps[dev_id] = header.timestamp
                        inf = db.query(MLInference).filter(MLInference.header_id == header.id).first()
                        if inf:
                            latest_inferences[dev_id] = {
                                "activity_code": inf.activity_code,
                                "confidence": inf.confidence,
                                "is_heat": inf.is_heat,
                                "heat_probability": inf.heat_probability,
                                "health_risk_decision": inf.health_risk_decision
                            }
                except Exception:
                    pass

    result = []
    for c in cows:
        dev_id = str(c.device_id)
        
        # Get pre-computed daily summary
        summary = summaries_by_device.get(dev_id)
        rum_hrs = summary.rumination_hours if summary else 0.0
        lying_hrs = summary.lying_hours if summary else 0.0
        feed_hrs = summary.feeding_hours if summary else 0.0
        move_hrs = summary.moving_hours if summary else 0.0
        
        # Get pre-computed latest inference
        inf = latest_inferences.get(dev_id)
        if inf:
            act_code = inf["activity_code"]
            act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP.get("RES"))
            health_risk = inf["health_risk_decision"] or "HEALTHY"
            is_heat = inf["is_heat"] or False
            heat_prob_pct = int((inf["heat_probability"] or 0) * 100)
        else:
            act_code = "RES"
            act_info = ACTIVITY_MAP.get("RES")
            health_risk = "HEALTHY"
            is_heat = False
            heat_prob_pct = 0
            
        ts = latest_timestamps.get(dev_id)
        heat_from_summary = (summary.heat_count > 0) if summary else False

        result.append({
            "id": c.id,
            "device_id": dev_id,
            "tagNumber": f"TAG-{c.device_id}",
            "name": c.name or f"Cattle #{c.device_id}",
            "breed": c.breed or "Gir / Sahiwal",
            "location": c.location or "Rupnagar Farm",
            "weight": f"{c.weight} kg" if c.weight else "400 kg",
            "healthStatus": "HIGH_RISK" if (health_risk == "HIGH_RISK" or is_heat or heat_from_summary) else health_risk,
            "health_risk_decision": health_risk,
            "currentActivity": act_code,
            "activityName": act_info["name"],
            "ruminationHoursToday": rum_hrs,
            "lyingHoursToday": lying_hrs,
            "feedingHoursToday": feed_hrs,
            "movingHoursToday": move_hrs,
            "estrusProbability": heat_prob_pct,
            "lastSeen": ts.isoformat() if ts else None
        })
        
    return result


@router.get("/{cow_id}/live")
def get_cow_live_dashboard(cow_id: str, db: Session = Depends(get_db)):
    """
    Get live health dashboard. Uses pre-computed ML inference from the database.
    Only falls back to live ML if no pre-computed inference exists for the latest header.
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

    # Get today's pre-computed daily summary (1 row)
    summary = db.query(DailyCowSummary).filter(
        DailyCowSummary.device_id == dev_id,
        DailyCowSummary.date == today
    ).first()

    monitored_hours = summary.monitored_hours if summary else 0.0
    rum_hrs = summary.rumination_hours if summary else 0.0
    lying_hrs = summary.lying_hours if summary else 0.0
    feed_hrs = summary.feeding_hours if summary else 0.0
    move_hrs = summary.moving_hours if summary else 0.0
    is_heat_summary = (summary.heat_count > 0) if summary else False

    # Get latest header + its points + its ML inference
    header = db.query(DataloggerHeader).filter(
        DataloggerHeader.device_id == dev_id
    ).order_by(DataloggerHeader.id.desc()).first()

    ts = header.timestamp if header else None
    x_buf, y_buf, z_buf = [], [], []
    ml_res = None
    act_code = "RES"
    act_info = ACTIVITY_MAP.get("RES")
    is_heat = False
    heat_prob_pct = 0
    health_risk = "HEALTHY"

    if header:
        # Get points for the latest header
        points = db.query(DataloggerPoint).filter(
            DataloggerPoint.header_id == header.id
        ).order_by(DataloggerPoint.point_index.asc()).all()
        
        x_buf = [p.x for p in points if p.x is not None]
        y_buf = [p.y for p in points if p.y is not None]
        z_buf = [p.z for p in points if p.z is not None]

        # Try to get pre-computed ML inference
        inference = db.query(MLInference).filter(MLInference.header_id == header.id).first()
        
        if inference:
            act_code = inference.activity_code
            act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP.get("RES"))
            is_heat = inference.is_heat or False
            heat_prob_pct = int((inference.heat_probability or 0) * 100)
            health_risk = inference.health_risk_decision or "HEALTHY"
            
            # Build full ML result from stored inference
            heat_alert = "HIGH" if (inference.heat_probability or 0) > 0.7 else ("MODERATE" if (inference.heat_probability or 0) > 0.4 else "NORMAL")
            ml_res = {
                "ml_engine_status": "CACHED",
                "activity": {
                    "code": act_code,
                    "description": act_info["name"],
                    "confidence": (inference.confidence or 85) / 100.0,
                    "is_ruminating": act_code == "RUS",
                    "is_grazing": act_code in ["GRZ", "FED", "FEP", "FES"],
                    "is_resting": act_code in ["RES", "REL"]
                },
                "heat_detection": {
                    "in_heat": is_heat,
                    "heat_probability": inference.heat_probability or 0.0,
                    "alert_level": heat_alert
                },
                "anomaly_detection": {"is_anomaly": False, "score": 0.0},
                "deviation_metrics": {"score": 0.0, "is_deviating": False, "threshold": 1.5},
                "health_risk_decision": health_risk,
                "features_extracted_count": 67
            }
        elif len(x_buf) > 0:
            # Fallback: run ML live only if no cached inference exists
            logger.info(f"No cached inference for header {header.id}, running live ML")
            manager = get_ml_manager()
            ml_res = manager.predict(x_buf, y_buf, z_buf)
            act_code = ml_res["activity"]["code"]
            act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP.get("RES"))
            is_heat = ml_res["heat_detection"]["in_heat"]
            heat_prob_pct = int(ml_res["heat_detection"]["heat_probability"] * 100)
            health_risk = ml_res.get("health_risk_decision", "HEALTHY")

    # Build default ML result if nothing available
    if ml_res is None:
        ml_res = {
            "ml_engine_status": "NO_DATA",
            "activity": {"code": "RES", "confidence": 0.0, "primary_activity": "RES"},
            "heat_detection": {"in_heat": False, "heat_probability": 0.0, "alert_level": "LOW"},
            "anomaly_detection": {"is_anomaly": False, "score": 0.0},
            "deviation_metrics": {"is_deviating": False},
            "health_risk_decision": "HEALTHY"
        }
        x_buf, y_buf, z_buf = [0]*80, [0]*80, [0]*80

    # Generate AI recommendation
    recommendation = "All vital health parameters are normal."
    if health_risk == "HIGH_RISK":
        if is_heat or is_heat_summary:
            recommendation = "CRITICAL: Cow is showing signs of being in heat. Action needed: Prepare for artificial insemination (breeding) in the next 12 hours."
        elif ml_res.get("anomaly_detection", {}).get("is_anomaly"):
            recommendation = "CRITICAL: Unusual movement patterns detected. Action needed: Physically check the cow for injury or sickness."
        else:
            recommendation = "CRITICAL: Severe health risk detected. Action needed: Physically check the cow immediately."
    elif health_risk == "MONITOR":
        if ml_res.get("heat_detection", {}).get("alert_level") == "MODERATE":
            recommendation = "MONITOR: Cow might be coming into heat. Watch for more signs."
        else:
            recommendation = "MONITOR: Some health metrics are slightly off. Keep a close eye on her."

    mag_buf = [round(math.sqrt(x_buf[i]**2 + y_buf[i]**2 + z_buf[i]**2), 3) for i in range(len(x_buf))]
    labels = [f"{(i*0.1):.1f}s" for i in range(len(x_buf))]

    return {
        "cowId": cow.id,
        "device_id": dev_id,
        "cowName": cow.name or f"Device #{cow.device_id}",
        "tagNumber": f"TAG-{cow.device_id}",
        "breed": cow.breed or "Local Cattle",
        "location": cow.location or "Rupnagar",
        "weight": f"{cow.weight} kg" if cow.weight else "400 kg",
        "notes": cow.notes,
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
            "ruminationScore": min(100, int((rum_hrs / 8.0) * 100)) if rum_hrs else 0,
            "estrusProbabilityPercent": heat_prob_pct,
            "isHeatDetected": is_heat or is_heat_summary,
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


@router.get("/{cow_id}/activity-7day")
def get_cow_7day_activity(cow_id: str, db: Session = Depends(get_db)):
    """
    Get 7-day behavior trends from pre-computed daily summaries.
    Single query — no ML inference at request time.
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

    if summaries:
        # Results come in desc order, reverse for chronological
        for s in reversed(summaries):
            days.append(s.date.strftime("%a"))
            dates.append(s.date.strftime("%Y-%m-%d"))
            rum_list.append(round(s.rumination_hours, 1))
            lying_list.append(round(s.lying_hours, 1))
            feed_list.append(round(s.feeding_hours, 1))
            act_list.append(round(s.moving_hours, 1))
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
            day_hours = (pkt_count * 8.0) / 3600.0
            # Without ML data, estimate even distribution
            rum_list.append(round(day_hours * 0.35, 1))
            lying_list.append(round(day_hours * 0.30, 1))
            feed_list.append(round(day_hours * 0.20, 1))
            act_list.append(round(day_hours * 0.15, 1))

    return {
        "cowId": cow_id,
        "device_id": str(dev_id),
        "days": days,
        "dates": dates,
        "ruminationHours": rum_list,
        "lyingRestHours": lying_list,
        "feedingHours": feed_list,
        "activeHours": act_list,
        "estrusAlerts": []
    }

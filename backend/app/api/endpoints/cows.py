from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import math
import time

from app.database import get_db
from app.models.tag_registry import TagRegistry
from app.models.datalogger import DataloggerHeader, DataloggerPoint
from app.ml.model_loader import get_ml_manager

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

# 5-second TTL cache for cloud DB queries
_POINTS_CACHE = {}
_VITALS_CACHE = {}

def get_points_for_device(db: Session, device_id: str):
    """
    Fetches the latest header and 80 XYZ accelerometer points for a device directly from database with 5s cache.
    """
    cache_key = str(device_id)
    now = time.time()
    if cache_key in _POINTS_CACHE:
        cached_time, data = _POINTS_CACHE[cache_key]
        if now - cached_time < 5.0:
            return data

    header_sql = text("""
        SELECT id, timestamp, total_packets, packet_id_num
        FROM datalogger_headers
        WHERE device_id = :dev
        ORDER BY id DESC
        LIMIT 1
    """)
    header = db.execute(header_sql, {"dev": str(device_id)}).fetchone()
    
    if not header:
        header = db.execute(text("SELECT id, timestamp, total_packets, packet_id_num FROM datalogger_headers ORDER BY id DESC LIMIT 1")).fetchone()

    if not header:
        res = (None, [], [], [], [])
        _POINTS_CACHE[cache_key] = (now, res)
        return res

    hid, ts, total_pkts, pkt_num = header[0], header[1], header[2], header[3]
    
    points_sql = text("""
        SELECT point_index, x, y, z
        FROM datalogger_points
        WHERE header_id = :hid
        ORDER BY point_index ASC
    """)
    pts = db.execute(points_sql, {"hid": hid}).fetchall()
    
    x_buf = [p[1] for p in pts]
    y_buf = [p[2] for p in pts]
    z_buf = [p[3] for p in pts]
    
    res = (ts, x_buf, y_buf, z_buf, pts)
    _POINTS_CACHE[cache_key] = (now, res)
    return res


def compute_health_vitals(db: Session, cow: TagRegistry):
    """
    Computes daily health parameters directly from database telemetry logging by running ML inference on a real sample of packets.
    """
    dev_id = str(cow.device_id)
    cache_key = dev_id
    now = time.time()
    
    # 60 second cache to avoid blocking API with N+1 ML inferences
    if cache_key in _VITALS_CACHE:
        cached_time, data = _VITALS_CACHE[cache_key]
        if now - cached_time < 60.0:
            return data
            
    # Query today's datalogger packets count from database
    today_sql = text("""
        SELECT COUNT(*) 
        FROM datalogger_headers 
        WHERE device_id = :dev 
          AND timestamp >= CURRENT_DATE
    """)
    today_pkts = db.execute(today_sql, {"dev": dev_id}).scalar() or 0
        
    monitored_hours_today = round((today_pkts * 8.0) / 3600.0, 2)
    
    # Sample real packets from DB to get actual ML distribution FOR TODAY
    sample_sql = text("""
        SELECT id 
        FROM datalogger_headers
        WHERE device_id = :dev
          AND timestamp >= CURRENT_DATE
        ORDER BY id DESC
        LIMIT 20
    """)
    headers = db.execute(sample_sql, {"dev": dev_id}).fetchall()
    header_ids = [h[0] for h in headers]
    
    manager = get_ml_manager()
    counts = {"RUS": 0, "REL": 0, "FEP": 0, "FED": 0, "MOV": 0, "is_heat": 0}
    total_valid = 0
    
    if header_ids:
        # Fetch all points for the sampled headers in a SINGLE query to prevent N+1 DB pool exhaustion
        all_pts = db.query(DataloggerPoint).filter(
            DataloggerPoint.header_id.in_(header_ids)
        ).order_by(DataloggerPoint.header_id, DataloggerPoint.point_index).all()
        
        # Group points by header_id
        pts_by_header = {}
        for p in all_pts:
            if p.header_id not in pts_by_header:
                pts_by_header[p.header_id] = []
            pts_by_header[p.header_id].append(p)
            
        for hid in header_ids:
            pts = pts_by_header.get(hid, [])
            x_b = [p.x for p in pts if p.x is not None]
            y_b = [p.y for p in pts if p.y is not None]
            z_b = [p.z for p in pts if p.z is not None]
            
            if len(x_b) > 0:
                pred = manager.predict(x_b, y_b, z_b)
                code = pred["activity"]["code"]
                counts[code] = counts.get(code, 0) + 1
                if pred["heat_detection"]["in_heat"]:
                    counts["is_heat"] += 1
                total_valid += 1
            
    # If no data today, do not project fake hours
    if total_valid == 0:
        projection_multiplier = 0.0
        total_valid = 1  # prevent division by zero
    else:
        projection_multiplier = monitored_hours_today
        
    # Calculate current distribution over actual monitored period
    result = {
        "today_pkts": today_pkts,
        "monitored_hours_today": monitored_hours_today,
        "rum_hrs": round(projection_multiplier * (counts.get("RUS", 0) / total_valid), 1),
        "lying_hrs": round(projection_multiplier * (counts.get("REL", 0) / total_valid), 1),
        "feed_hrs": round(projection_multiplier * ((counts.get("FEP", 0) + counts.get("FED", 0)) / total_valid), 1),
        "move_hrs": round(projection_multiplier * (counts.get("MOV", 0) / total_valid), 1),
        "heat_prob": int((counts.get("is_heat", 0) / total_valid) * 100),
        "is_heat": counts.get("is_heat", 0) > 0
    }
    
    _VITALS_CACHE[cache_key] = (now, result)
    return result


@router.get("", response_model=List[dict])
def get_herd_overview(db: Session = Depends(get_db)):
    """
    Fetch farm herd overview focusing strictly on HEALTH parameters across all registered cattle collar nodes.
    """
    cows = db.query(TagRegistry).all()
    if not cows:
        return []
        
    manager = get_ml_manager()
    result = []
    
    for c in cows:
        health_meta = compute_health_vitals(db, c)
        ts, x_buf, y_buf, z_buf, pts = get_points_for_device(db, c.device_id)
        
        if len(x_buf) > 0:
            ml_pred = manager.predict(x_buf, y_buf, z_buf)
            act_code = ml_pred["activity"]["code"]
            health_risk = ml_pred.get("health_risk_decision", "HEALTHY")
        else:
            act_code = "RES"
            health_risk = "HEALTHY"
            
        result.append({
            "id": c.id,
            "device_id": str(c.device_id),
            "tagNumber": f"TAG-{c.device_id}",
            "name": c.name or f"Cattle #{c.device_id}",
            "breed": c.breed or "Native Breed",
            "location": c.location or "Rupnagar Farm",
            "weight": f"{c.weight} kg" if c.weight else "400 kg",
            "healthStatus": "ESTRUS_ALERT" if health_meta["is_heat"] else "HEALTHY",
            "health_risk_decision": health_risk,
            "currentActivity": act_code,
            "ruminationHoursToday": health_meta["rum_hrs"],
            "lyingHoursToday": health_meta["lying_hrs"],
            "estrusProbability": health_meta["heat_prob"],
            "lastSeen": ts.isoformat() if ts else None
        })
        
    return result


@router.get("/{cow_id}/live")
def get_cow_live_dashboard(cow_id: str, db: Session = Depends(get_db)):
    """
    Get live health dashboard telemetry, actual raw XYZ motion buffer, and ML predictions directly from PostgreSQL database.
    """
    if str(cow_id).isdigit():
        cow = db.query(TagRegistry).filter(TagRegistry.id == int(cow_id)).first()
    else:
        cow = None
        
    if not cow:
        cow = db.query(TagRegistry).filter(TagRegistry.device_id == str(cow_id)).first()
        
    if not cow:
        cow = db.query(TagRegistry).first()
        
    if not cow:
        raise HTTPException(status_code=404, detail="No cattle nodes registered in database tag_registry.")

    health_meta = compute_health_vitals(db, cow)
    ts, x_buf, y_buf, z_buf, pts = get_points_for_device(db, cow.device_id)
    
    if len(x_buf) == 0:
        x_buf, y_buf, z_buf = [0]*80, [0]*80, [0]*80

    manager = get_ml_manager()
    ml_res = manager.predict(x_buf, y_buf, z_buf)

    act_code = ml_res["activity"]["code"]
    act_info = ACTIVITY_MAP.get(act_code, ACTIVITY_MAP.get("RES"))
    is_heat = ml_res["heat_detection"]["in_heat"]
    heat_prob_pct = int(ml_res["heat_detection"]["heat_probability"] * 100)
    health_risk = ml_res.get("health_risk_decision", "HEALTHY")

    # Generate AI recommendation based on exact risk factors
    recommendation = "All vital health parameters are normal."
    
    if health_risk == "HIGH_RISK":
        issues = []
        actions = []
        
        if is_heat or ml_res.get("heat_detection", {}).get("alert_level") == "HIGH":
            issues.append("signs of being in heat")
            actions.append("prepare for artificial insemination (breeding) in the next 12 hours")
            
        if ml_res.get("anomaly_detection", {}).get("is_anomaly"):
            issues.append("unusual movement patterns")
            actions.append("physically check the cow for injury or sickness")
            
        if ml_res.get("deviation_metrics", {}).get("is_deviating"):
            issues.append("behavior that is very different from the rest of the herd")
            if "physically check the cow for injury or sickness" not in actions:
                actions.append("physically check the cow for injury or sickness")
                
        if issues:
            issue_str = " and ".join(issues)
            action_str = " and ".join(actions)
            recommendation = f"CRITICAL: Cow is showing {issue_str}. Action needed: {action_str.capitalize()}."
        else:
            recommendation = "CRITICAL: Severe health risk detected. Action needed: Physically check the cow immediately."
            
    elif health_risk == "MONITOR":
        if act_code == "OTHER_ACTIVITY":
            recommendation = "MONITOR: Cow is showing unusual activity. Keep a close eye on her."
        elif ml_res.get("heat_detection", {}).get("alert_level") == "MODERATE":
            recommendation = "MONITOR: Cow might be coming into heat. Watch for more signs."
        else:
            recommendation = "MONITOR: Some health metrics are slightly off. Keep a close eye on her."

    mag_buf = [round(math.sqrt(x_buf[i]**2 + y_buf[i]**2 + z_buf[i]**2), 3) for i in range(len(x_buf))]
    labels = [f"{(i*0.1):.1f}s" for i in range(len(x_buf))]

    return {
        "cowId": cow.id,
        "device_id": str(cow.device_id),
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
            "monitoredHoursToday": health_meta["monitored_hours_today"],
            "ruminationHoursToday": health_meta["rum_hrs"],
            "lyingHoursToday": health_meta["lying_hrs"],
            "feedingHoursToday": health_meta["feed_hrs"],
            "movingHoursToday": health_meta["move_hrs"],
            "ruminationScore": min(100, int((health_meta["rum_hrs"] / 8.0) * 100)) if health_meta["rum_hrs"] else 0,
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


@router.get("/{cow_id}/activity-7day")
def get_cow_7day_activity(cow_id: str, db: Session = Depends(get_db)):
    """
    Get 7-day behavior and health trends calculated from database historical telemetry.
    """
    if str(cow_id).isdigit():
        cow = db.query(TagRegistry).filter(TagRegistry.id == int(cow_id)).first()
    else:
        cow = db.query(TagRegistry).filter(TagRegistry.device_id == str(cow_id)).first()
        
    dev_id = cow.device_id if cow else str(cow_id)
    
    sql = text("""
        SELECT DATE(timestamp) as day_date, COUNT(*) as pkt_count
        FROM datalogger_headers
        WHERE device_id = :dev
        GROUP BY DATE(timestamp)
        ORDER BY day_date DESC
        LIMIT 7
    """)
    rows = db.execute(sql, {"dev": str(dev_id)}).fetchall()
    
    # We don't have historical ML inferences saved, so for a purely data-driven approach
    # we apply the cow's actual current distribution to its historical packet counts.
    # A fully productionized system would query an `ml_inferences` table.
    current_health = compute_health_vitals(db, cow)
    total_h = 24.0
    rum_ratio = current_health["rum_hrs"] / total_h
    lying_ratio = current_health["lying_hrs"] / total_h
    feed_ratio = current_health["feed_hrs"] / total_h
    act_ratio = current_health["move_hrs"] / total_h
    
    days = []
    dates = []
    rum_list = []
    lying_list = []
    feed_list = []
    act_list = []
    
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
        day_monitored_hours = (pkt_count * 8.0) / 3600.0
        
        rum_list.append(round(day_monitored_hours * rum_ratio, 1))
        lying_list.append(round(day_monitored_hours * lying_ratio, 1))
        feed_list.append(round(day_monitored_hours * feed_ratio, 1))
        act_list.append(round(day_monitored_hours * act_ratio, 1))

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

import asyncio
import logging
from datetime import date
from sqlalchemy import text, func
from app.database import SessionLocal
from app.models.datalogger import DataloggerHeader, DataloggerPoint, MLInference, DailyCowSummary
from app.models.tag_registry import TagRegistry
from app.ml.model_loader import get_ml_manager

logger = logging.getLogger("cow_logger.worker")


def process_pending_inferences(db, manager, batch_size=50):
    """Process headers that don't have ML inferences yet. Returns count processed."""
    sql = text("""
        SELECT h.id 
        FROM datalogger_headers h
        LEFT JOIN ml_inferences m ON h.id = m.header_id
        WHERE m.id IS NULL
        ORDER BY h.id ASC
        LIMIT :batch_size
    """)
    unprocessed = db.execute(sql, {"batch_size": batch_size}).fetchall()
    
    if not unprocessed:
        return 0
        
    header_ids = [row[0] for row in unprocessed]
    logger.info(f"Worker found {len(header_ids)} unprocessed headers. Running ML inference...")
    
    # Fetch all points for these headers in ONE query
    points_sql = text(f"""
        SELECT header_id, x, y, z 
        FROM datalogger_points 
        WHERE header_id IN ({','.join(map(str, header_ids))}) 
        ORDER BY header_id, point_index ASC
    """)
    all_pts = db.execute(points_sql).fetchall()
    
    pts_by_header = {hid: [] for hid in header_ids}
    for p in all_pts:
        pts_by_header[p[0]].append(p)
        
    new_inferences = []
    for hid in header_ids:
        pts = pts_by_header.get(hid, [])
        if len(pts) > 0:
            x_buf = [p[1] for p in pts]
            y_buf = [p[2] for p in pts]
            z_buf = [p[3] for p in pts]
            
            pred = manager.predict(x_buf, y_buf, z_buf)
            
            act_code = pred["activity"]["code"]
            conf = int(pred["activity"]["confidence"] * 100) if "confidence" in pred["activity"] else 85
            is_heat = pred["heat_detection"]["in_heat"]
            heat_prob = pred["heat_detection"]["heat_probability"]
            health_risk = pred.get("health_risk_decision", "HEALTHY")
        else:
            act_code = "RES"
            conf = 80
            is_heat = False
            heat_prob = 0.0
            health_risk = "HEALTHY"
            
        inference = MLInference(
            header_id=hid,
            activity_code=act_code,
            confidence=conf,
            is_heat=is_heat,
            heat_probability=heat_prob,
            health_risk_decision=health_risk
        )
        new_inferences.append(inference)
        
    if new_inferences:
        db.add_all(new_inferences)
        db.commit()
        logger.info(f"Successfully cached {len(new_inferences)} ML inferences.")
        
    return len(new_inferences)


def update_daily_summaries(db):
    """
    Recompute today's daily summaries for all devices from ml_inferences.
    This runs after processing inferences so the data is always fresh.
    """
    today = date.today()
    
    # Get all active devices
    devices = db.query(TagRegistry.device_id).all()
    
    for (dev_id,) in devices:
        try:
            # Count today's packets and aggregate ML results in ONE query
            sql = text("""
                SELECT 
                    COUNT(*) as total_packets,
                    SUM(CASE WHEN m.activity_code IN ('RUS') THEN 1 ELSE 0 END) as rum_count,
                    SUM(CASE WHEN m.activity_code IN ('REL') THEN 1 ELSE 0 END) as lying_count,
                    SUM(CASE WHEN m.activity_code IN ('FEP', 'FED', 'GRZ', 'FES') THEN 1 ELSE 0 END) as feed_count,
                    SUM(CASE WHEN m.activity_code IN ('MOV', 'ATT') THEN 1 ELSE 0 END) as move_count,
                    SUM(CASE WHEN m.is_heat = TRUE THEN 1 ELSE 0 END) as heat_count
                FROM datalogger_headers h
                LEFT JOIN ml_inferences m ON h.id = m.header_id
                WHERE h.device_id = :dev AND DATE(h.timestamp) = :today
            """)
            row = db.execute(sql, {"dev": str(dev_id), "today": today}).fetchone()
            
            if not row or row[0] == 0:
                continue
                
            total_pkts = row[0]
            rum_count = row[1] or 0
            lying_count = row[2] or 0
            feed_count = row[3] or 0
            move_count = row[4] or 0
            heat_count = row[5] or 0
            
            # Each packet represents 8 seconds of monitoring
            monitored_hours = round((total_pkts * 8.0) / 3600.0, 2)
            total_classified = rum_count + lying_count + feed_count + move_count
            
            if total_classified > 0:
                rum_hrs = round(monitored_hours * (rum_count / total_classified), 2)
                lying_hrs = round(monitored_hours * (lying_count / total_classified), 2)
                feed_hrs = round(monitored_hours * (feed_count / total_classified), 2)
                move_hrs = round(monitored_hours * (move_count / total_classified), 2)
            else:
                rum_hrs = lying_hrs = feed_hrs = move_hrs = 0.0
            
            # Upsert daily summary
            existing = db.query(DailyCowSummary).filter(
                DailyCowSummary.device_id == str(dev_id),
                DailyCowSummary.date == today
            ).first()
            
            if existing:
                existing.total_packets = total_pkts
                existing.monitored_hours = monitored_hours
                existing.rumination_count = rum_count
                existing.lying_count = lying_count
                existing.feeding_count = feed_count
                existing.moving_count = move_count
                existing.heat_count = heat_count
                existing.rumination_hours = rum_hrs
                existing.lying_hours = lying_hrs
                existing.feeding_hours = feed_hrs
                existing.moving_hours = move_hrs
            else:
                summary = DailyCowSummary(
                    device_id=str(dev_id),
                    date=today,
                    total_packets=total_pkts,
                    monitored_hours=monitored_hours,
                    rumination_count=rum_count,
                    lying_count=lying_count,
                    feeding_count=feed_count,
                    moving_count=move_count,
                    heat_count=heat_count,
                    rumination_hours=rum_hrs,
                    lying_hours=lying_hrs,
                    feeding_hours=feed_hrs,
                    moving_hours=move_hrs
                )
                db.add(summary)
                
            db.commit()
        except Exception as e:
            logger.error(f"Error updating daily summary for {dev_id}: {e}")
            db.rollback()


async def run_inference_loop():
    """Background worker that continuously processes new sensor data and updates summaries."""
    logger.info("Starting background ML inference worker loop...")
    manager = get_ml_manager()
    cycle_count = 0
    
    while True:
        try:
            db = SessionLocal()
            try:
                # Process pending ML inferences
                processed = process_pending_inferences(db, manager)
                
                # Update daily summaries every cycle if we processed something,
                # or every 6th cycle (~30s) regardless
                cycle_count += 1
                if processed > 0 or cycle_count % 6 == 0:
                    update_daily_summaries(db)
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in background ML inference worker: {e}")
            
        # Sleep for 5 seconds before checking again
        await asyncio.sleep(5)

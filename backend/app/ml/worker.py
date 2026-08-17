import asyncio
import logging
from sqlalchemy import text
from app.database import SessionLocal
from app.models.datalogger import DataloggerHeader, DataloggerPoint, MLInference
from app.ml.model_loader import get_ml_manager

logger = logging.getLogger("cow_logger.worker")

async def run_inference_loop():
    logger.info("Starting background ML inference worker loop...")
    while True:
        try:
            db = SessionLocal()
            try:
                # Find up to 50 headers that do NOT have an entry in ml_inferences
                # We use a simple LEFT JOIN where ml_inferences.id IS NULL
                sql = text("""
                    SELECT h.id 
                    FROM datalogger_headers h
                    LEFT JOIN ml_inferences m ON h.id = m.header_id
                    WHERE m.id IS NULL
                    ORDER BY h.id ASC
                    LIMIT 50
                """)
                unprocessed = db.execute(sql).fetchall()
                
                if unprocessed:
                    header_ids = [row[0] for row in unprocessed]
                    logger.info(f"Worker found {len(header_ids)} unprocessed headers. Running ML inference...")
                    
                    # Fetch all points for these headers
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
                        
                    manager = get_ml_manager()
                    
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
                        logger.info(f"Successfully processed and cached {len(new_inferences)} ML inferences.")
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in background ML inference worker: {e}")
            
        # Sleep for 5 seconds before checking again
        await asyncio.sleep(5)

"""
Sync and compute full 7-day historical telemetry and ML inferences for all AWS collar devices.
Fetches raw packets from AWS Lambda, runs ML predictions, computes daily summaries,
and writes to PostgreSQL DailyCowSummary and SystemCache snapshot.
"""
import os
import sys
import time
import json
from datetime import datetime, date, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from app.services.aws_service import AwsTelemetryService, _parse_timestamp, AWS_PACKET_INTERVAL_SECONDS, _save_snapshot
from app.ml.model_loader import get_ml_manager
from app.database import SessionLocal
from app.models.datalogger import DailyCowSummary, SystemCache

def main():
    print("=== Starting Full 7-Day AWS Telemetry & ML Ingest ===", flush=True)
    mgr = get_ml_manager()
    print(f"ML Manager loaded: {mgr.is_loaded}", flush=True)

    # Dynamic date range: current rolling 7 days up to today (UTC)
    today = datetime.now(timezone.utc).date()
    date_range = [today - timedelta(days=i) for i in range(6, -1, -1)]

    # Dynamic device list: from CLI arguments if specified, else dynamically discovered
    if len(sys.argv) > 1:
        devices = [d.replace("aws-", "").strip() for d in sys.argv[1:] if d.strip()]
    else:
        print("Auto-discovering active AWS collar devices...", flush=True)
        discovered = AwsTelemetryService.discover_devices(force=True)
        known = AwsTelemetryService.get_known_device_ids()
        candidate_devs = sorted(list(set(known) | set(discovered)), key=lambda x: int(x) if str(x).isdigit() else str(x))
        # Filter to devices that have transmitted data within the rolling 7-day window
        active_devs = [d for d in candidate_devs if AwsTelemetryService.device_has_7day_data(d)]
        devices = active_devs if active_devs else candidate_devs

    print(f"Dates to process: {[d.strftime('%Y-%m-%d') for d in date_range]}", flush=True)
    print(f"Dynamically resolved active devices: {devices}", flush=True)

    db = SessionLocal()
    total_synced = 0

    try:
        for dev_id in devices:
            print(f"\n--- Processing Device AWS-{dev_id} ---", flush=True)
            for d in date_range:
                d_aws_fmt = d.strftime("%d-%m-%Y")
                d_str = d.strftime("%Y-%m-%d")

                t0 = time.time()
                raw_pkts = AwsTelemetryService.fetch_aws_raw(dev_id, start_date=d_aws_fmt, end_date=d_aws_fmt)
                fetch_dt = time.time() - t0
                tot = len(raw_pkts)

                aws_db_id = f"aws-{dev_id}"
                if tot == 0:
                    # Check if DB already has verified historical data for this date
                    existing = db.query(DailyCowSummary).filter(
                        DailyCowSummary.device_id == aws_db_id,
                        DailyCowSummary.date == d
                    ).first()
                    if existing and (existing.monitored_hours or 0) > 0:
                        print(f"  [{d_str}] 0 pkts from API, but DB has {existing.monitored_hours}h — preserving DB record", flush=True)
                        continue

                    print(f"  [{d_str}] 0 packets ({fetch_dt:.1f}s)", flush=True)
                    if not existing:
                        db.add(DailyCowSummary(
                            device_id=aws_db_id,
                            date=d,
                            total_packets=0,
                            monitored_hours=0.0,
                            rumination_hours=0.0,
                            lying_hours=0.0,
                            feeding_hours=0.0,
                            moving_hours=0.0,
                            heat_count=0
                        ))
                    AwsTelemetryService._update_daily_summary_from_packets(dev_id, d, [])
                    continue

                # Process packets through ML
                processed = []
                for pkt in raw_pkts:
                    raw_pts = pkt.get("Data", [])
                    if len(raw_pts) < 3:
                        continue
                    dt = _parse_timestamp(pkt)
                    epoch_val = int(pkt.get("Epoch", dt.timestamp()))
                    x_buf = [float(raw_pts[j]) for j in range(0, len(raw_pts), 3)]
                    y_buf = [float(raw_pts[j+1]) for j in range(0, len(raw_pts), 3)]
                    z_buf = [float(raw_pts[j+2]) for j in range(0, len(raw_pts), 3)]
                    pred = mgr.predict(x_buf, y_buf, z_buf)
                    processed.append({
                        "device_id": str(dev_id),
                        "timestamp": dt,
                        "epoch": epoch_val,
                        "ml_inference": pred
                    })

                proc_dt = time.time() - t0
                first_epoch = processed[0]["epoch"]
                last_epoch = processed[-1]["epoch"]
                span_hrs = (last_epoch - first_epoch) / 3600.0 if last_epoch > first_epoch else (tot * 45) / 3600.0
                mon_hrs = min(24.0, round(max(span_hrs, (tot * 45) / 3600.0), 2))

                c_rus = sum(1 for p in processed if p.get("ml_inference", {}).get("activity", {}).get("code") == "RUS")
                c_rel = sum(1 for p in processed if p.get("ml_inference", {}).get("activity", {}).get("code") == "REL")
                c_fep = sum(1 for p in processed if p.get("ml_inference", {}).get("activity", {}).get("code") in ["FEP", "FED", "GRZ"])
                c_mov = sum(1 for p in processed if p.get("ml_inference", {}).get("activity", {}).get("code") == "MOV")
                c_heat = sum(1 for p in processed if p.get("ml_inference", {}).get("heat_detection", {}).get("in_heat"))

                r_hrs = min(mon_hrs, round((c_rus / tot) * mon_hrs, 2)) if tot > 0 else 0.0
                l_hrs = min(mon_hrs, round((c_rel / tot) * mon_hrs, 2)) if tot > 0 else 0.0
                f_hrs = min(mon_hrs, round((c_fep / tot) * mon_hrs, 2)) if tot > 0 else 0.0
                m_hrs = min(mon_hrs, round((c_mov / tot) * mon_hrs, 2)) if tot > 0 else 0.0

                # Update in-memory summary
                AwsTelemetryService._update_daily_summary_from_packets(dev_id, d, processed)

                # Persist to PostgreSQL DailyCowSummary
                existing = db.query(DailyCowSummary).filter(
                    DailyCowSummary.device_id == aws_db_id,
                    DailyCowSummary.date == d
                ).first()

                if not existing:
                    db.add(DailyCowSummary(
                        device_id=aws_db_id,
                        date=d,
                        total_packets=tot,
                        monitored_hours=mon_hrs,
                        rumination_hours=r_hrs,
                        lying_hours=l_hrs,
                        feeding_hours=f_hrs,
                        moving_hours=m_hrs,
                        heat_count=c_heat
                    ))
                else:
                    existing.total_packets = tot
                    existing.monitored_hours = mon_hrs
                    existing.rumination_hours = r_hrs
                    existing.lying_hours = l_hrs
                    existing.feeding_hours = f_hrs
                    existing.moving_hours = m_hrs
                    existing.heat_count = c_heat

                db.commit()
                total_synced += 1
                print(f"  [{d_str}] {tot} pkts -> Monitored: {mon_hrs}h, Rum: {r_hrs}h, Lying: {l_hrs}h, Move: {m_hrs}h ({proc_dt:.1f}s)", flush=True)

        print(f"\nSuccessfully synced {total_synced} daily summaries to PostgreSQL!", flush=True)

        # Re-compute 7-day breakdown and transition logs for all 5 devices and save snapshot
        print("\nRe-computing 7-day dashboards and transition logs...", flush=True)
        for dev_id in devices:
            res_7d = AwsTelemetryService._refresh_7day_and_logs(dev_id)
            logs = AwsTelemetryService.get_activity_logs(dev_id, page=1, limit=250)
            print(f"  Dev {dev_id}: 7-day monitored={res_7d.get('monitoredHours')}, logs={len(logs.get('logs', []))}", flush=True)

        # Force save snapshot to PostgreSQL SystemCache and disk
        _save_snapshot()
        print("\n=== Snapshot saved to PostgreSQL SystemCache and disk successfully! ===", flush=True)

    finally:
        db.close()

if __name__ == "__main__":
    main()

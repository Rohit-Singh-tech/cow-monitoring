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

from app.services.aws_service import (
    AwsTelemetryService,
    _parse_timestamp,
    AWS_PACKET_INTERVAL_SECONDS,
    _save_snapshot,
    IST
)
from app.ml.model_loader import get_ml_manager
from app.database import SessionLocal
from app.models.datalogger import DailyCowSummary, SystemCache

def main():
    print("=== Starting Full 7-Day AWS Telemetry & ML Ingest ===", flush=True)
    mgr = get_ml_manager()
    print(f"ML Manager loaded: {mgr.is_loaded}", flush=True)

    # Dynamic date range: current rolling 7 days up to today in Indian Standard Time (IST)
    today = datetime.now(IST).date()
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
                    if existing and (existing.monitored_hours or 0) > 0 and getattr(existing, "is_finalized", False):
                        print(f"  [{d_str}] 0 pkts from API, but DB has finalized {existing.monitored_hours}h — preserving DB record", flush=True)
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
                        db.commit()
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
                # Use unified calculation from AwsTelemetryService
                metrics = AwsTelemetryService._calculate_day_metrics(processed)
                mon_hrs = metrics["monitored_hours"]
                r_hrs = metrics["rum_hours"]
                l_hrs = metrics["lying_hours"]
                f_hrs = metrics["feed_hours"]
                m_hrs = metrics["move_hours"]
                c_heat = metrics["heat_count"]
                tot_pkts = metrics["total_packets"]

                # Update in-memory summary
                AwsTelemetryService._update_daily_summary_from_packets(dev_id, d, processed)

                # Persist to PostgreSQL DailyCowSummary
                existing = db.query(DailyCowSummary).filter(
                    DailyCowSummary.device_id == aws_db_id,
                    DailyCowSummary.date == d
                ).first()

                is_fin = bool(d < today)

                if not existing:
                    db.add(DailyCowSummary(
                        device_id=aws_db_id,
                        date=d,
                        total_packets=tot_pkts,
                        monitored_hours=mon_hrs,
                        rumination_hours=r_hrs,
                        lying_hours=l_hrs,
                        feeding_hours=f_hrs,
                        moving_hours=m_hrs,
                        heat_count=c_heat,
                        is_finalized=is_fin
                    ))
                else:
                    if getattr(existing, "is_finalized", False) and (d < today) and (existing.monitored_hours or 0.0) >= 22.0 and mon_hrs < (existing.monitored_hours or 0.0):
                        continue
                    existing.total_packets = tot_pkts
                    existing.monitored_hours = mon_hrs
                    existing.rumination_hours = r_hrs
                    existing.lying_hours = l_hrs
                    existing.feeding_hours = f_hrs
                    existing.moving_hours = m_hrs
                    existing.heat_count = c_heat
                    existing.is_finalized = is_fin

                db.commit()
                total_synced += 1
                print(f"  [{d_str}] {tot_pkts} pkts -> Monitored: {mon_hrs}h, Rum: {r_hrs}h, Lying: {l_hrs}h, Feed: {f_hrs}h, Move: {m_hrs}h ({proc_dt:.1f}s)", flush=True)

        print(f"\nSuccessfully synced {total_synced} daily summaries to PostgreSQL!", flush=True)

        # Re-compute 7-day breakdown and transition logs for all active devices and save snapshot
        print("\nRe-computing 7-day dashboards, live diagnostics, and transition logs...", flush=True)
        for dev_id in devices:
            res_7d = AwsTelemetryService._refresh_7day_and_logs(dev_id)
            AwsTelemetryService._compute_live_dashboard(dev_id)
            logs = AwsTelemetryService.get_activity_logs(dev_id, page=1, limit=250)
            print(f"  Dev {dev_id}: 7-day monitored={res_7d.get('monitoredHours')}, logs={len(logs.get('logs', []))}", flush=True)

        # Force save snapshot to PostgreSQL SystemCache and disk
        _save_snapshot()
        print("\n=== Snapshot saved to PostgreSQL SystemCache and disk successfully! ===", flush=True)

    finally:
        db.close()

if __name__ == "__main__":
    main()

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/hardware-specs")
def get_hardware_specs():
    """
    Get hardware specs, nRF52832 BLE collar specs, and SPI Flash ring buffer metrics.
    """
    return {
        "node_info": {
            "microcontroller": "Nordic Semiconductor nRF52832 BLE SoC",
            "accelerometer": "STMicroelectronics LIS3DH 3-Axis Accelerometer",
            "sampling_frequency": "10 Hz (100 ms sampling interval)",
            "local_storage": "8 MB SPI External Flash (W25Q64)",
            "packet_capacity": 32768,
            "packet_size_bytes": 256,
            "current_packet_count": 14250,
            "storage_filled_percent": 43.5,
            "max_logging_duration_hours": 72.8,
            "power_source": "3.7V 5400 mAh Li-Ion Rechargeable Battery",
            "average_current_draw_ua": 98.16,
            "estimated_battery_years": 6.28
        },
        "knock_knock_security": {
            "protocol_section": "6.7",
            "status": "SCANNABLE_BEACON_MODE",
            "authorized_dump_signature": "0x59 0x00 0xBB 0xCC",
            "authorized_reset_signature": "0x59 0x00 0xFF 0xFF",
            "description": "Collar node remains in ultra-low-power BLE scannable beacon mode. High-speed data replay is initiated only after receiving authorized knock-knock trigger signature."
        },
        "iit_ropar_project": {
            "title": "Gateway Less Cow Health Monitoring System",
            "lead_org": "AWaDH Hub, IIT Ropar",
            "partner_orgs": ["GADVASU", "NABARD"],
            "features_extracted_count": 78
        }
    }

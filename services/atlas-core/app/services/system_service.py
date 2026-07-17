import time

import psutil


def get_system_status() -> dict:
    return {
        "host": "Hermes II",
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "load_average": list(psutil.getloadavg()),
    }

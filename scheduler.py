"""
Dedicated SLA state scheduler service.

Runs as a background process to scan open tickets and transition SLA states
(Healthy -> Approaching -> Breached).
Handles SIGINT and SIGTERM gracefully.
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime, timezone

from app import create_app
from app.services.sla import SLAService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger("helpdesk.scheduler")

# Flag for graceful shutdown
running = True


def handle_shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received (%s). Stopping scheduler...", signum)
    running = False


def main():
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    interval = int(os.environ.get("SLA_SCAN_INTERVAL_SECONDS", 60))
    logger.info("Starting Beyond2U SLA Scheduler Service (Interval: %ds)", interval)

    app = create_app()

    with app.app_context():
        while running:
            try:
                logger.debug("Executing scheduled SLA scan...")
                SLAService.scan_and_update()
            except Exception as e:
                logger.error("Error during SLA scan execution: %s", str(e), exc_info=True)

            # Sleep in short increments to allow quick shutdown response
            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)

    logger.info("SLA Scheduler Service stopped cleanly.")


if __name__ == "__main__":
    main()

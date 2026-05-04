"""Root entry point for Survey & Excel Intelligence MCP."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

load_dotenv()

from app.config import settings
from app.logging_config import logger
from app.server import mcp


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  Survey & Excel Intelligence MCP")
    logger.info("  Excel karşılaştırma · Anket analizi · Grafik · Rapor")
    logger.info("=" * 60)
    logger.info("  Endpoint  : http://%s:%s%s", settings.MCP_HOST, settings.MCP_PORT, settings.MCP_PATH)
    logger.info("  Transport : %s", settings.MCP_TRANSPORT)
    logger.info("  Data Dir  : %s", settings.DATA_DIR)
    logger.info("  Outputs   : %s", settings.OUTPUT_DIR)
    logger.info("=" * 60)

    mcp.run(
        transport=settings.MCP_TRANSPORT,
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        path=settings.MCP_PATH,
    )

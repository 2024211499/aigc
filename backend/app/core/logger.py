# -*- coding: utf-8 -*-
"""日志配置"""

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO"):
    log_dir = Path(__file__).parent.parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
    ]

    logging.basicConfig(level=getattr(logging, level), format=fmt, handlers=handlers)

    # 抑制第三方库噪音
    for noisy in ["httpx", "httpcore", "openai", "chromadb", "urllib3"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

import sys
from pathlib import Path
from typing import Any, Optional

import loguru
import loguru._logger

logger = loguru.logger


def setup_logger(
    output_dir: Optional[Path] = None,
    bind: dict[str, Any] = {},
    stderr_level: str = "INFO",
    file_level: str = "DEBUG",
    # ) -> "loguru.Logger":
) -> None:
    _logger = loguru.logger.bind(**bind)
    _logger.remove()
    format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        " - <level>{message}</level>"
        " - {extra}"
    )
    _logger.add(sys.stdout, colorize=True, format=format, level=stderr_level)
    if output_dir is not None:
        _logger.add(
            output_dir / "output.log",
            backtrace=True,
            diagnose=True,
            format=format,
        )
        _logger.add(
            output_dir / "output.jsonl", serialize=True, level=file_level
        )
        _logger.info(f"Use logger output_dir: {str(output_dir)}")

    global logger
    logger = _logger

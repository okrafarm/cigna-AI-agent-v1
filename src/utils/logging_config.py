import sys
from pathlib import Path
from loguru import logger
from src.config.settings import Settings


def setup_logging(settings: Settings = None):
    """Configure logging for the application"""
    
    # Remove default logger
    logger.remove()
    
    # Console logging with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Main application log
    logger.add(
        logs_dir / "cigna_agent.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="1 day",
        retention="30 days",
        compression="zip"
    )
    
    # Error-only log for quick debugging
    logger.add(
        logs_dir / "errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="1 week",
        retention="12 weeks",
        compression="zip"
    )
    
    # WhatsApp specific log
    logger.add(
        logs_dir / "whatsapp.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        filter=lambda record: "whatsapp" in record["name"].lower(),
        level="INFO",
        rotation="1 day",
        retention="14 days"
    )
    
    # Cigna automation log
    logger.add(
        logs_dir / "cigna_automation.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        filter=lambda record: "cigna" in record["name"].lower(),
        level="DEBUG",
        rotation="1 day",
        retention="14 days"
    )
    
    # Performance log for monitoring
    logger.add(
        logs_dir / "performance.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
        filter=lambda record: "performance" in record["extra"],
        level="INFO",
        rotation="1 day",
        retention="7 days"
    )
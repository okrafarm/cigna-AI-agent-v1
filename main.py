#!/usr/bin/env python3

import asyncio
import signal
from pathlib import Path
from loguru import logger

from src.config.settings import get_settings, setup_directories
from src.database.models import ClaimDatabase
from src.whatsapp.handler import WhatsAppHandler
from src.cigna_automation.claim_processor import ClaimProcessor
from src.utils.export import CSVExporter
from src.utils.logging_config import setup_logging
from src.utils.error_handling import error_tracker, safe_async_task


class CignaClaimAgent:
    def __init__(self):
        self.settings = get_settings()
        self.running = False
        self.db = None
        self.whatsapp_handler = None
        self.claim_processor = None
        self.csv_exporter = None
        
    async def startup(self):
        logger.info("Starting Cigna Claim Agent...")
        
        try:
            # Setup directories
            setup_directories(self.settings)
            
            # Initialize database
            self.db = ClaimDatabase(self.settings.database_path)
            await self.db.connect()
            logger.info(f"Database connected: {self.settings.database_path}")
            
            # Initialize components
            self.whatsapp_handler = WhatsAppHandler(self.settings, self.db)
            self.claim_processor = ClaimProcessor(self.settings, self.db)
            self.csv_exporter = CSVExporter(self.settings, self.db)
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Cigna Claim Agent: {e}")
            error_tracker.record_error(e, {'phase': 'startup'})
            raise
        
    async def shutdown(self):
        logger.info("Shutting down Cigna Claim Agent...")
        self.running = False
        
        if self.db:
            await self.db.close()
            
        logger.info("Shutdown complete")
        
    async def run(self):
        await self.startup()
        self.running = True
        
        # Start background tasks with safe error handling
        tasks = [
            asyncio.create_task(safe_async_task(self.whatsapp_handler.start_listening())),
            asyncio.create_task(safe_async_task(self.claim_processor.process_claims_loop())),
            asyncio.create_task(safe_async_task(self.csv_exporter.export_loop()))
        ]
        
        try:
            logger.info("Agent is now running. Press Ctrl+C to stop.")
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            # Cancel all tasks
            for task in tasks:
                task.cancel()
            
            await self.shutdown()


def handle_signal(agent):
    def _handler(signum, frame):
        logger.info(f"Received signal {signum}")
        agent.running = False
    return _handler


async def main():
    agent = CignaClaimAgent()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, handle_signal(agent))
    signal.signal(signal.SIGTERM, handle_signal(agent))
    
    await agent.run()


if __name__ == "__main__":
    # Setup logging first
    setup_logging()
    
    logger.info("Starting Cigna International Claim Filing Agent")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        error_tracker.record_error(e, {'phase': 'main'})
        raise
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from loguru import logger
from asyncio_throttle import Throttler

from src.config.settings import Settings
from src.database.models import ClaimDatabase, Claim, ClaimStatus
from src.cigna_automation.cigna_bot import CignaBot, CignaBotError


class ClaimProcessor:
    def __init__(self, settings: Settings, db: ClaimDatabase):
        self.settings = settings
        self.db = db
        self.throttler = Throttler(rate_limit=1, period=5)  # 1 request per 5 seconds
        self._running = False
        
    async def process_claims_loop(self):
        """Main processing loop for handling claims"""
        self._running = True
        logger.info("Started claim processing loop")
        
        while self._running:
            try:
                # Process new claims (submit to Cigna)
                await self._process_new_claims()
                
                # Check status of submitted claims
                await self._check_submitted_claims()
                
                # Wait before next iteration
                await asyncio.sleep(self.settings.claim_check_interval)
                
            except Exception as e:
                logger.error(f"Error in claim processing loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
                
        logger.info("Claim processing loop stopped")
        
    async def _process_new_claims(self):
        """Process claims that haven't been submitted yet"""
        try:
            # Get claims that are ready to be processed
            new_claims = await self.db.get_claims_by_status(ClaimStatus.RECEIVED)
            
            if not new_claims:
                return
                
            logger.info(f"Found {len(new_claims)} new claims to process")
            
            # Process claims with concurrency limit
            semaphore = asyncio.Semaphore(self.settings.max_concurrent_claims)
            tasks = [
                self._process_single_claim(claim, semaphore)
                for claim in new_claims
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Error processing new claims: {e}")
            
    async def _process_single_claim(self, claim: Claim, semaphore: asyncio.Semaphore):
        """Process a single claim submission"""
        async with semaphore:
            try:
                # Throttle requests to avoid overwhelming Cigna's servers
                async with self.throttler:
                    await self._submit_claim_to_cigna(claim)
                    
            except Exception as e:
                logger.error(f"Failed to process claim {claim.id}: {e}")
                await self.db.update_claim_status(
                    claim.id,
                    ClaimStatus.ERROR,
                    error_message=str(e)
                )
                
    async def _submit_claim_to_cigna(self, claim: Claim):
        """Submit a single claim to Cigna website"""
        logger.info(f"Submitting claim {claim.id} to Cigna")
        
        # Update status to processing
        await self.db.update_claim_status(claim.id, ClaimStatus.PROCESSING)
        
        async with CignaBot(self.settings) as bot:
            try:
                # Submit the claim
                cigna_claim_number = await bot.submit_claim(
                    claim.extracted_data,
                    claim.bill_image_path
                )
                
                # Update claim with Cigna claim number and submitted status
                await self.db.update_claim_status(
                    claim.id,
                    ClaimStatus.SUBMITTED,
                    cigna_claim_number=cigna_claim_number
                )
                
                logger.info(f"Successfully submitted claim {claim.id}, Cigna claim: {cigna_claim_number}")
                
            except CignaBotError as e:
                logger.error(f"Cigna bot error for claim {claim.id}: {e}")
                await self.db.update_claim_status(
                    claim.id,
                    ClaimStatus.ERROR,
                    error_message=f"Cigna submission failed: {e}"
                )
                
            except Exception as e:
                logger.error(f"Unexpected error submitting claim {claim.id}: {e}")
                await self.db.update_claim_status(
                    claim.id,
                    ClaimStatus.ERROR,
                    error_message=f"Submission error: {e}"
                )
                
    async def _check_submitted_claims(self):
        """Check status of claims that have been submitted to Cigna"""
        try:
            # Get submitted claims that need status updates
            submitted_claims = await self.db.get_claims_by_status(ClaimStatus.SUBMITTED)
            processing_claims = await self.db.get_claims_by_status(ClaimStatus.PROCESSING)
            
            all_pending_claims = submitted_claims + processing_claims
            
            if not all_pending_claims:
                return
                
            logger.info(f"Checking status of {len(all_pending_claims)} pending claims")
            
            # Check status with rate limiting
            semaphore = asyncio.Semaphore(2)  # Lower concurrency for status checks
            tasks = [
                self._check_single_claim_status(claim, semaphore)
                for claim in all_pending_claims
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Error checking claim statuses: {e}")
            
    async def _check_single_claim_status(self, claim: Claim, semaphore: asyncio.Semaphore):
        """Check status of a single claim"""
        async with semaphore:
            try:
                if not claim.cigna_claim_number:
                    return
                    
                # Throttle status checks
                async with self.throttler:
                    await self._update_claim_status_from_cigna(claim)
                    
            except Exception as e:
                logger.error(f"Failed to check status for claim {claim.id}: {e}")
                
    async def _update_claim_status_from_cigna(self, claim: Claim):
        """Update claim status by checking Cigna website"""
        logger.debug(f"Checking status for claim {claim.id}, Cigna: {claim.cigna_claim_number}")
        
        async with CignaBot(self.settings) as bot:
            try:
                # Get status from Cigna
                status_info = await bot.check_claim_status(claim.cigna_claim_number)
                
                if status_info.get("status") == "error":
                    logger.warning(f"Could not check status for claim {claim.id}: {status_info.get('error')}")
                    return
                    
                # Map Cigna status to our internal status
                cigna_status = status_info.get("status", "").lower()
                new_status = self._map_cigna_status(cigna_status)
                
                # Only update if status has changed
                if new_status != claim.status:
                    settlement_amount = status_info.get("settlement_amount")
                    settlement_currency = status_info.get("settlement_currency")
                    
                    await self.db.update_claim_status(
                        claim.id,
                        new_status,
                        settlement_amount=settlement_amount,
                        settlement_currency=settlement_currency
                    )
                    
                    logger.info(f"Updated claim {claim.id} status from {claim.status.value} to {new_status.value}")
                    
            except CignaBotError as e:
                logger.error(f"Cigna bot error checking claim {claim.id}: {e}")
                
            except Exception as e:
                logger.error(f"Unexpected error checking claim {claim.id}: {e}")
                
    def _map_cigna_status(self, cigna_status: str) -> ClaimStatus:
        """Map Cigna status strings to our internal status enum"""
        status_mapping = {
            'approved': ClaimStatus.APPROVED,
            'rejected': ClaimStatus.REJECTED,
            'denied': ClaimStatus.REJECTED,
            'paid': ClaimStatus.PAID,
            'processing': ClaimStatus.PROCESSING,
            'submitted': ClaimStatus.SUBMITTED,
            'pending': ClaimStatus.PROCESSING
        }
        
        return status_mapping.get(cigna_status, ClaimStatus.PROCESSING)
        
    async def stop(self):
        """Stop the claim processing loop"""
        self._running = False
        logger.info("Stopping claim processor")
        
    async def process_claim_manually(self, claim_id: int) -> bool:
        """Manually process a specific claim"""
        try:
            claim = await self.db.get_claim_by_id(claim_id)
            if not claim:
                logger.error(f"Claim {claim_id} not found")
                return False
                
            semaphore = asyncio.Semaphore(1)
            await self._process_single_claim(claim, semaphore)
            return True
            
        except Exception as e:
            logger.error(f"Error manually processing claim {claim_id}: {e}")
            return False
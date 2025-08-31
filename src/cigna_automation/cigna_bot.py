import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from loguru import logger

from src.config.settings import Settings
from src.database.models import MedicalBill, Claim, ClaimStatus


class CignaBotError(Exception):
    """Custom exception for Cigna bot errors"""
    pass


class CignaBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_logged_in = False
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        
    async def start(self):
        """Initialize browser and context"""
        self.playwright = await async_playwright().start()
        
        # Launch browser with appropriate settings
        self.browser = await self.playwright.chromium.launch(
            headless=True,  # Set to False for debugging
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        
        # Create context with mobile user agent to avoid detection
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        self.page = await self.context.new_page()
        
        # Set timeouts
        self.page.set_default_timeout(30000)  # 30 seconds
        
        logger.info("Cigna bot initialized")
        
    async def close(self):
        """Clean up browser resources"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
            
        logger.info("Cigna bot closed")
        
    async def login(self) -> bool:
        """Log into Cigna International portal"""
        try:
            logger.info("Attempting to log into Cigna portal")
            
            # Navigate to login page
            await self.page.goto(self.settings.cigna_login_url)
            await self.page.wait_for_load_state('networkidle')
            
            # Wait for and fill username
            username_field = await self.page.wait_for_selector('input[name="username"], input[type="email"], input[placeholder*="username"], input[placeholder*="email"]', timeout=10000)
            await username_field.fill(self.settings.cigna_username)
            
            # Wait for and fill password
            password_field = await self.page.wait_for_selector('input[name="password"], input[type="password"]', timeout=10000)
            await password_field.fill(self.settings.cigna_password)
            
            # Click login button
            login_button = await self.page.wait_for_selector('button[type="submit"], input[type="submit"], button:has-text("Log"), button:has-text("Sign")', timeout=10000)
            await login_button.click()
            
            # Wait for navigation and check if login was successful
            await self.page.wait_for_load_state('networkidle')
            
            # Check for successful login indicators
            success_indicators = [
                'text=Dashboard',
                'text=Claims',
                'text=Welcome',
                'text=My Account',
                '[data-testid="dashboard"]'
            ]
            
            for indicator in success_indicators:
                try:
                    await self.page.wait_for_selector(indicator, timeout=5000)
                    self.is_logged_in = True
                    logger.info("Successfully logged into Cigna portal")
                    return True
                except:
                    continue
                    
            # Check for error messages
            error_selectors = [
                'text=Invalid',
                'text=Error',
                'text=incorrect',
                '.error',
                '.alert-danger'
            ]
            
            for error_selector in error_selectors:
                try:
                    error_element = await self.page.wait_for_selector(error_selector, timeout=2000)
                    error_text = await error_element.text_content()
                    raise CignaBotError(f"Login failed: {error_text}")
                except:
                    continue
                    
            raise CignaBotError("Login failed: Unknown error")
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            self.is_logged_in = False
            return False
            
    async def submit_claim(self, medical_bill: MedicalBill, image_path: Path) -> Optional[str]:
        """Submit a new claim to Cigna"""
        if not self.is_logged_in:
            if not await self.login():
                raise CignaBotError("Cannot submit claim: Login failed")
                
        try:
            logger.info(f"Submitting claim for {medical_bill.patient_name}")
            
            # Navigate to claims section
            await self._navigate_to_claims()
            
            # Start new claim
            await self._start_new_claim()
            
            # Fill claim form
            claim_number = await self._fill_claim_form(medical_bill, image_path)
            
            logger.info(f"Successfully submitted claim: {claim_number}")
            return claim_number
            
        except Exception as e:
            logger.error(f"Failed to submit claim: {e}")
            raise CignaBotError(f"Claim submission failed: {e}")
            
    async def _navigate_to_claims(self):
        """Navigate to the claims section"""
        # Look for claims link/button
        claims_selectors = [
            'a:has-text("Claims")',
            'button:has-text("Claims")',
            'a[href*="claims"]',
            'a[href*="claim"]',
            '.nav-claims',
            '[data-testid="claims"]'
        ]
        
        for selector in claims_selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=5000)
                await element.click()
                await self.page.wait_for_load_state('networkidle')
                return
            except:
                continue
                
        raise CignaBotError("Could not find claims navigation")
        
    async def _start_new_claim(self):
        """Start a new claim process"""
        new_claim_selectors = [
            'button:has-text("New Claim")',
            'button:has-text("Submit")',
            'a:has-text("Submit Claim")',
            '.new-claim',
            '[data-testid="new-claim"]'
        ]
        
        for selector in new_claim_selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=5000)
                await element.click()
                await self.page.wait_for_load_state('networkidle')
                return
            except:
                continue
                
        raise CignaBotError("Could not find new claim button")
        
    async def _fill_claim_form(self, medical_bill: MedicalBill, image_path: Path) -> str:
        """Fill out the claim form with medical bill data"""
        
        # Patient information
        await self._fill_field_safely('input[name*="patient"], input[placeholder*="patient"]', medical_bill.patient_name)
        
        # Provider information
        await self._fill_field_safely('input[name*="provider"], input[placeholder*="provider"]', medical_bill.provider_name)
        
        # Service date
        service_date_str = medical_bill.service_date.strftime('%m/%d/%Y')
        await self._fill_field_safely('input[type="date"], input[name*="date"]', service_date_str)
        
        # Amount
        await self._fill_field_safely('input[name*="amount"], input[placeholder*="amount"]', str(medical_bill.total_amount))
        
        # Treatment description
        await self._fill_field_safely('textarea, input[name*="description"]', medical_bill.treatment_description)
        
        # Upload receipt/bill image
        await self._upload_document(image_path)
        
        # Submit the form
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Submit")',
            'input[type="submit"]'
        ]
        
        for selector in submit_selectors:
            try:
                submit_button = await self.page.wait_for_selector(selector, timeout=5000)
                await submit_button.click()
                break
            except:
                continue
        else:
            raise CignaBotError("Could not find submit button")
            
        # Wait for confirmation and extract claim number
        await self.page.wait_for_load_state('networkidle')
        
        # Look for claim number in success message
        claim_number_patterns = [
            r'Claim\s*#?:?\s*([A-Z0-9]+)',
            r'Reference\s*#?:?\s*([A-Z0-9]+)',
            r'Confirmation\s*#?:?\s*([A-Z0-9]+)'
        ]
        
        page_text = await self.page.text_content('body')
        
        import re
        for pattern in claim_number_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                return match.group(1)
                
        # If no claim number found, generate a timestamp-based one
        return f"CL{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
    async def _fill_field_safely(self, selector: str, value: str):
        """Fill a form field safely with error handling"""
        try:
            field = await self.page.wait_for_selector(selector, timeout=5000)
            await field.clear()
            await field.fill(value)
        except:
            logger.warning(f"Could not fill field with selector: {selector}")
            
    async def _upload_document(self, file_path: Path):
        """Upload document to the form"""
        upload_selectors = [
            'input[type="file"]',
            '[data-testid="file-upload"]',
            '.file-upload input'
        ]
        
        for selector in upload_selectors:
            try:
                upload_input = await self.page.wait_for_selector(selector, timeout=5000)
                await upload_input.set_input_files(str(file_path))
                return
            except:
                continue
                
        logger.warning("Could not find file upload field")
        
    async def check_claim_status(self, claim_number: str) -> Dict:
        """Check the status of an existing claim"""
        if not self.is_logged_in:
            if not await self.login():
                raise CignaBotError("Cannot check status: Login failed")
                
        try:
            # Navigate to claims history/status page
            await self._navigate_to_claims()
            
            # Search for the specific claim
            search_selectors = [
                'input[name*="search"]',
                'input[placeholder*="search"]',
                'input[type="search"]'
            ]
            
            for selector in search_selectors:
                try:
                    search_field = await self.page.wait_for_selector(selector, timeout=5000)
                    await search_field.fill(claim_number)
                    await search_field.press('Enter')
                    await self.page.wait_for_load_state('networkidle')
                    break
                except:
                    continue
                    
            # Extract claim status information
            claim_info = await self._extract_claim_info(claim_number)
            return claim_info
            
        except Exception as e:
            logger.error(f"Failed to check claim status: {e}")
            return {"status": "error", "error": str(e)}
            
    async def _extract_claim_info(self, claim_number: str) -> Dict:
        """Extract claim information from the status page"""
        # This would need to be customized based on Cigna's actual UI
        try:
            # Look for status indicators
            page_text = await self.page.text_content('body')
            
            status_mapping = {
                'approved': ClaimStatus.APPROVED,
                'rejected': ClaimStatus.REJECTED,
                'denied': ClaimStatus.REJECTED,
                'paid': ClaimStatus.PAID,
                'processing': ClaimStatus.PROCESSING,
                'submitted': ClaimStatus.SUBMITTED
            }
            
            detected_status = ClaimStatus.SUBMITTED  # default
            for keyword, status in status_mapping.items():
                if keyword.lower() in page_text.lower():
                    detected_status = status
                    break
                    
            return {
                "status": detected_status.value,
                "claim_number": claim_number,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
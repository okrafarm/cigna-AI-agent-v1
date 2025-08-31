import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
import aiofiles
import httpx
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from loguru import logger

from src.config.settings import Settings
from src.database.models import ClaimDatabase, Claim, MedicalBill, ClaimStatus
from src.document_processor.extractor import DocumentExtractor


class WhatsAppHandler:
    def __init__(self, settings: Settings, db: ClaimDatabase):
        self.settings = settings
        self.db = db
        self.twilio_client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token
        )
        self.document_extractor = DocumentExtractor(settings)
        self.http_client = httpx.AsyncClient()
        
    async def start_listening(self):
        """Start listening for WhatsApp messages via webhook"""
        logger.info("WhatsApp handler started - webhook mode")
        
        # In a real implementation, this would set up a Flask/FastAPI server
        # to receive webhooks from Twilio. For now, we'll simulate periodic checking
        while True:
            await asyncio.sleep(10)  # Check every 10 seconds
            
    async def handle_incoming_message(self, message_data: dict) -> MessagingResponse:
        """Handle incoming WhatsApp message"""
        try:
            message_sid = message_data.get('MessageSid')
            from_number = message_data.get('From')
            body = message_data.get('Body', '')
            media_url = message_data.get('MediaUrl0')
            
            logger.info(f"Received message from {from_number}: {body}")
            
            response = MessagingResponse()
            
            if not media_url:
                response.message("Please send a photo of your medical bill.")
                return response
                
            # Download and process the image
            image_path = await self._download_image(message_sid, media_url)
            if not image_path:
                response.message("Sorry, I couldn't download the image. Please try again.")
                return response
                
            # Extract data from the medical bill
            try:
                extracted_data = await self.document_extractor.extract_bill_data(image_path)
                
                # Create new claim record
                claim = Claim(
                    id=None,
                    whatsapp_message_id=message_sid,
                    bill_image_path=str(image_path),
                    extracted_data=extracted_data,
                    status=ClaimStatus.RECEIVED,
                    cigna_claim_number=None,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
                claim_id = await self.db.insert_claim(claim)
                
                # Send confirmation message
                confirmation = self._format_confirmation_message(extracted_data, claim_id)
                response.message(confirmation)
                
                logger.info(f"Created claim {claim_id} for message {message_sid}")
                
            except Exception as e:
                logger.error(f"Error processing bill image: {e}")
                response.message("Sorry, I couldn't process your medical bill. Please ensure the image is clear and contains all necessary information.")
                
        except Exception as e:
            logger.error(f"Error handling WhatsApp message: {e}")
            response = MessagingResponse()
            response.message("Sorry, there was an error processing your message. Please try again.")
            
        return response
        
    async def _download_image(self, message_sid: str, media_url: str) -> Optional[Path]:
        """Download image from WhatsApp media URL"""
        try:
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{message_sid}_{timestamp}.jpg"
            file_path = self.settings.upload_dir / filename
            
            # Download the image
            auth = (self.settings.twilio_account_sid, self.settings.twilio_auth_token)
            async with self.http_client.get(media_url, auth=auth) as response:
                if response.status_code == 200:
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.aiter_bytes():
                            await f.write(chunk)
                    
                    logger.info(f"Downloaded image to {file_path}")
                    return file_path
                else:
                    logger.error(f"Failed to download image: HTTP {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None
            
    def _format_confirmation_message(self, bill_data: MedicalBill, claim_id: int) -> str:
        """Format confirmation message for WhatsApp"""
        return f"""✅ Medical bill received and processed!

📋 **Claim ID**: {claim_id}
🏥 **Provider**: {bill_data.provider_name}
👤 **Patient**: {bill_data.patient_name}
📅 **Service Date**: {bill_data.service_date.strftime('%Y-%m-%d')}
💰 **Amount**: {bill_data.total_amount} {bill_data.currency}
🩺 **Treatment**: {bill_data.treatment_description}

I'll now submit this claim to Cigna International automatically. You'll receive updates on the claim status.

To check status anytime, reply with: STATUS {claim_id}"""

    async def send_status_update(self, to_number: str, claim: Claim):
        """Send claim status update to WhatsApp user"""
        try:
            status_message = self._format_status_message(claim)
            
            message = self.twilio_client.messages.create(
                from_=self.settings.twilio_whatsapp_number,
                body=status_message,
                to=to_number
            )
            
            logger.info(f"Sent status update for claim {claim.id} to {to_number}")
            
        except Exception as e:
            logger.error(f"Error sending WhatsApp status update: {e}")
            
    def _format_status_message(self, claim: Claim) -> str:
        """Format status update message"""
        status_emoji = {
            ClaimStatus.RECEIVED: "📥",
            ClaimStatus.PROCESSING: "⏳", 
            ClaimStatus.SUBMITTED: "📤",
            ClaimStatus.APPROVED: "✅",
            ClaimStatus.REJECTED: "❌",
            ClaimStatus.PAID: "💰",
            ClaimStatus.ERROR: "⚠️"
        }
        
        emoji = status_emoji.get(claim.status, "📋")
        
        message = f"""{emoji} **Claim Update**

📋 **Claim ID**: {claim.id}
📊 **Status**: {claim.status.value.upper()}
🏥 **Provider**: {claim.extracted_data.provider_name}
💰 **Amount**: {claim.extracted_data.total_amount} {claim.extracted_data.currency}"""

        if claim.cigna_claim_number:
            message += f"\n🔢 **Cigna Claim #**: {claim.cigna_claim_number}"
            
        if claim.settlement_amount:
            message += f"\n💸 **Settlement**: {claim.settlement_amount} {claim.settlement_currency}"
            
        if claim.error_message:
            message += f"\n⚠️ **Error**: {claim.error_message}"
            
        message += f"\n📅 **Updated**: {claim.updated_at.strftime('%Y-%m-%d %H:%M')}"
        
        return message
        
    async def close(self):
        """Clean up resources"""
        await self.http_client.aclose()
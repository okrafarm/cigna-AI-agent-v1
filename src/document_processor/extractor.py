import asyncio
import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional
import pytesseract
from PIL import Image
import pdf2image
from openai import AsyncOpenAI
from loguru import logger

from src.config.settings import Settings
from src.database.models import MedicalBill


class DocumentExtractor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Configure Tesseract path if provided
        if settings.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path
            
    async def extract_bill_data(self, image_path: Path) -> MedicalBill:
        """Extract structured data from medical bill image"""
        logger.info(f"Processing document: {image_path}")
        
        # Step 1: Extract raw text using OCR
        raw_text = await self._extract_text_from_image(image_path)
        logger.debug(f"Extracted raw text length: {len(raw_text)}")
        
        # Step 2: Use AI to structure the extracted text
        structured_data = await self._structure_bill_data(raw_text)
        
        # Step 3: Convert to MedicalBill object
        medical_bill = self._create_medical_bill(structured_data)
        
        logger.info(f"Successfully extracted bill data for {medical_bill.patient_name}")
        return medical_bill
        
    async def _extract_text_from_image(self, image_path: Path) -> str:
        """Extract text from image using OCR"""
        try:
            def _ocr_extraction():
                # Handle different file types
                if image_path.suffix.lower() == '.pdf':
                    # Convert PDF to images first
                    images = pdf2image.convert_from_path(image_path)
                    full_text = ""
                    for image in images:
                        text = pytesseract.image_to_string(image, lang='eng')
                        full_text += text + "\n"
                    return full_text
                else:
                    # Process as image
                    image = Image.open(image_path)
                    return pytesseract.image_to_string(image, lang='eng')
            
            # Run OCR in thread pool to avoid blocking
            raw_text = await asyncio.to_thread(_ocr_extraction)
            return raw_text.strip()
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise
            
    async def _structure_bill_data(self, raw_text: str) -> Dict[str, Any]:
        """Use OpenAI to structure the raw OCR text into medical bill data"""
        
        system_prompt = """You are an expert at extracting structured data from medical bills and receipts. 
        
        Extract the following information from the provided medical bill text and return it as a JSON object:

        {
            "provider_name": "Name of the medical provider/hospital/clinic",
            "patient_name": "Full name of the patient",
            "service_date": "Date of service in YYYY-MM-DD format",
            "total_amount": "Total amount as a number (no currency symbols)",
            "currency": "Currency code (e.g., USD, EUR, SGD)",
            "diagnosis_codes": ["Array of diagnosis codes if available"],
            "treatment_description": "Description of treatment/services provided",
            "receipt_number": "Receipt or invoice number if available",
            "additional_info": {
                "doctor_name": "Doctor's name if available",
                "insurance_info": "Any insurance information mentioned",
                "payment_method": "How payment was made if mentioned"
            }
        }

        Rules:
        1. If a field is not found, use null for strings, 0 for amounts, empty array for lists
        2. For dates, try to infer the year if not provided (use current year)
        3. Convert all monetary amounts to numbers (remove currency symbols and formatting)
        4. Extract all diagnosis codes you can find (ICD-10, etc.)
        5. Be conservative - only extract information you're confident about
        6. If multiple currencies are mentioned, use the one associated with the total amount
        """

        user_prompt = f"""Please extract structured data from this medical bill:

        {raw_text}

        Return only the JSON object, no additional text."""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Extract JSON from response
            content = response.choices[0].message.content.strip()
            
            # Remove potential markdown formatting
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
                
            structured_data = json.loads(content)
            logger.debug("Successfully structured bill data with AI")
            return structured_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"AI structuring failed: {e}")
            raise
            
    def _create_medical_bill(self, data: Dict[str, Any]) -> MedicalBill:
        """Convert structured data dictionary to MedicalBill object"""
        try:
            # Parse service date
            service_date_str = data.get('service_date')
            if service_date_str:
                try:
                    service_date = date.fromisoformat(service_date_str)
                except ValueError:
                    # Fallback to current date if parsing fails
                    service_date = date.today()
            else:
                service_date = date.today()
                
            # Ensure required fields have defaults
            provider_name = data.get('provider_name') or "Unknown Provider"
            patient_name = data.get('patient_name') or "Unknown Patient"
            total_amount = float(data.get('total_amount', 0))
            currency = data.get('currency') or "USD"
            
            # Handle diagnosis codes
            diagnosis_codes = data.get('diagnosis_codes', [])
            if isinstance(diagnosis_codes, str):
                diagnosis_codes = [diagnosis_codes]
            elif not isinstance(diagnosis_codes, list):
                diagnosis_codes = []
                
            return MedicalBill(
                provider_name=provider_name,
                patient_name=patient_name,
                service_date=service_date,
                total_amount=total_amount,
                currency=currency,
                diagnosis_codes=diagnosis_codes,
                treatment_description=data.get('treatment_description') or "Medical services",
                receipt_number=data.get('receipt_number'),
                additional_info=data.get('additional_info')
            )
            
        except Exception as e:
            logger.error(f"Error creating MedicalBill object: {e}")
            # Return a basic medical bill with minimal info
            return MedicalBill(
                provider_name="Unknown Provider",
                patient_name="Unknown Patient", 
                service_date=date.today(),
                total_amount=0.0,
                currency="USD",
                diagnosis_codes=[],
                treatment_description="Medical services",
                additional_info={"extraction_error": str(e)}
            )
#!/usr/bin/env python3
"""
Medical Billing Image Renamer

Automatically renames medical billing images based on OCR-extracted content.
Generates meaningful filenames with provider, date, and document type information.
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

import pytesseract
from PIL import Image
import cv2
import numpy as np
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class MedicalImageRenamer:
    """Renames medical billing images based on OCR content analysis."""
    
    def __init__(self):
        self.input_dir = Path(os.getenv('INPUT_DIR', './input_images'))
        self.output_dir = Path(os.getenv('OUTPUT_DIR', './output_images'))
        self.tesseract_cmd = os.getenv('TESSERACT_CMD', 'tesseract')
        self.date_format = os.getenv('DATE_FORMAT', '%Y%m%d')
        self.confidence_threshold = int(os.getenv('OCR_CONFIDENCE_THRESHOLD', '30'))
        self.max_filename_length = int(os.getenv('MAX_FILENAME_LENGTH', '100'))
        
        # Keywords for detection
        self.provider_keywords = [
            word.strip().lower() 
            for word in os.getenv('PROVIDER_KEYWORDS', 'cigna,aetna,anthem,bcbs,humana,kaiser,united,uhc').split(',')
        ]
        self.document_types = [
            word.strip().lower() 
            for word in os.getenv('DOCUMENT_TYPES', 'eob,claim,statement,bill,invoice,receipt').split(',')
        ]
        self.patient_keywords = [
            word.strip().lower() 
            for word in os.getenv('PATIENT_KEYWORDS', 'patient,member,subscriber,name,insured').split(',')
        ]
        self.hospital_keywords = [
            word.strip().lower() 
            for word in os.getenv('HOSPITAL_KEYWORDS', 'hospital,medical center,clinic,health system,healthcare,provider,billing entity').split(',')
        ]
        self.amount_keywords = [
            word.strip().lower() 
            for word in os.getenv('AMOUNT_KEYWORDS', 'total,amount,balance,due,charge,bill,cost,payment').split(',')
        ]
        
        # Set tesseract command path
        if self.tesseract_cmd != 'tesseract':
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        
        # Create directories
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info(f"Initialized Medical Image Renamer")
        logger.info(f"Input directory: {self.input_dir}")
        logger.info(f"Output directory: {self.output_dir}")
    
    def preprocess_image(self, image_path: Path) -> np.ndarray:
        """Preprocess image to improve OCR accuracy."""
        try:
            # Read image
            img = cv2.imread(str(image_path))
            if img is None:
                raise ValueError("Could not load image")
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply denoising
            denoised = cv2.fastNlMeansDenoising(gray)
            
            # Apply thresholding to get better text contrast
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return thresh
            
        except Exception as e:
            logger.warning(f"Image preprocessing failed for {image_path}: {e}")
            # Fall back to original image
            img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            return img
    
    def extract_text(self, image_path: Path) -> str:
        """Extract text from image using OCR."""
        try:
            # Preprocess image
            processed_img = self.preprocess_image(image_path)
            
            # Convert numpy array to PIL Image
            pil_img = Image.fromarray(processed_img)
            
            # Perform OCR with confidence data
            ocr_data = pytesseract.image_to_data(
                pil_img, 
                output_type=pytesseract.Output.DICT,
                config='--psm 6'  # Uniform block of text
            )
            
            # Filter text by confidence
            filtered_text = []
            for i in range(len(ocr_data['text'])):
                confidence = int(ocr_data['conf'][i])
                text = ocr_data['text'][i].strip()
                if confidence > self.confidence_threshold and text:
                    filtered_text.append(text)
            
            return ' '.join(filtered_text)
            
        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
            return ""
    
    def extract_date(self, text: str) -> Optional[str]:
        """Extract date from OCR text."""
        # Common date patterns
        date_patterns = [
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',  # MM/DD/YYYY or MM-DD-YYYY
            r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',  # YYYY/MM/DD or YYYY-MM-DD
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2})\b',  # MM/DD/YY or MM-DD-YY
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})\b',  # Month DD, YYYY
        ]
        
        for pattern in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    groups = match.groups()
                    if len(groups) == 3:
                        if pattern == date_patterns[3]:  # Month name pattern
                            month_name, day, year = groups
                            date_obj = datetime.strptime(f"{month_name} {day} {year}", "%b %d %Y")
                        else:
                            # Try different date formats
                            date_str = match.group()
                            for fmt in ['%m/%d/%Y', '%Y/%m/%d', '%m-%d-%Y', '%Y-%m-%d', '%m/%d/%y', '%m-%d-%y']:
                                try:
                                    date_obj = datetime.strptime(date_str, fmt)
                                    if date_obj.year < 2000 and date_obj.year > 50:  # Handle 2-digit years
                                        date_obj = date_obj.replace(year=date_obj.year + 1900)
                                    elif date_obj.year < 50:
                                        date_obj = date_obj.replace(year=date_obj.year + 2000)
                                    break
                                except ValueError:
                                    continue
                            else:
                                continue
                        
                        return date_obj.strftime(self.date_format)
                        
                except ValueError:
                    continue
        
        return None
    
    def extract_patient_name(self, text: str) -> Optional[str]:
        """Extract patient name from OCR text."""
        lines = text.split('\n')
        
        # Look for lines containing patient keywords
        for line in lines:
            line_lower = line.lower()
            for keyword in self.patient_keywords:
                if keyword in line_lower:
                    # Try to extract name after the keyword
                    patterns = [
                        rf'{keyword}\s*:?\s*([A-Za-z\s,]+)',
                        rf'([A-Za-z\s,]+)\s*{keyword}',
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            name = match.group(1).strip()
                            # Clean up the name
                            name = re.sub(r'[^A-Za-z\s]', '', name)
                            name = re.sub(r'\s+', ' ', name).strip()
                            if len(name) > 3 and len(name) < 50:  # Reasonable name length
                                return name.title()
        
        # Look for capitalized names (common format)
        name_patterns = [
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b',  # First Last
            r'\b([A-Z][a-z]+,\s*[A-Z][a-z]+)\b',  # Last, First
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                name = match.replace(',', '').strip()
                if len(name) > 3 and len(name) < 50:
                    return name.title()
        
        return None
    
    def extract_hospital_name(self, text: str) -> Optional[str]:
        """Extract hospital/billing entity name from OCR text."""
        lines = text.split('\n')
        
        # Look for lines containing hospital keywords
        for line in lines:
            line_lower = line.lower()
            for keyword in self.hospital_keywords:
                if keyword in line_lower:
                    # Clean the line and extract entity name
                    cleaned_line = re.sub(r'[^A-Za-z\s]', ' ', line)
                    cleaned_line = re.sub(r'\s+', ' ', cleaned_line).strip()
                    if len(cleaned_line) > 5 and len(cleaned_line) < 80:
                        return cleaned_line.title()
        
        # Look for medical facility patterns
        facility_patterns = [
            r'\b([A-Z][A-Za-z\s]+(?:Hospital|Medical Center|Clinic|Health System|Healthcare))\b',
            r'\b([A-Z][A-Za-z\s]{5,40})\s+(?:Hospital|Medical|Clinic|Health)\b',
        ]
        
        for pattern in facility_patterns:
            match = re.search(pattern, text)
            if match:
                facility = match.group(1).strip()
                if len(facility) > 5:
                    return facility.title()
        
        return None
    
    def extract_bill_amount(self, text: str) -> Optional[str]:
        """Extract bill amount from OCR text."""
        # Look for dollar amounts
        amount_patterns = [
            r'\$([0-9,]+\.?[0-9]*)',  # $123.45 or $1,234
            r'([0-9,]+\.?[0-9]*)\s*(?:USD|dollars?)',  # 123.45 USD
            r'(?:total|amount|balance|due|charge|bill|cost|payment)\s*:?\s*\$?([0-9,]+\.?[0-9]*)',
        ]
        
        amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Clean the amount
                amount = re.sub(r'[^0-9.,]', '', match)
                if '.' in amount or ',' in amount:
                    try:
                        # Convert to float to validate
                        float_amount = float(amount.replace(',', ''))
                        if 0 < float_amount < 999999:  # Reasonable medical bill range
                            amounts.append(amount)
                    except ValueError:
                        continue
        
        if amounts:
            # Return the largest amount found (likely the total)
            largest = max(amounts, key=lambda x: float(x.replace(',', '')))
            return f"${largest}"
        
        return None
    
    def extract_provider(self, text: str) -> Optional[str]:
        """Extract insurance provider from OCR text."""
        text_lower = text.lower()
        
        for provider in self.provider_keywords:
            if provider in text_lower:
                return provider.title()
        
        # Look for common insurance company patterns
        insurance_patterns = [
            r'\b([A-Z][a-z]+)\s+(Health|Insurance|Medical)\b',
            r'\b(Blue\s+Cross|Blue\s+Shield)\b',
        ]
        
        for pattern in insurance_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group().title()
        
        return None
    
    def extract_document_type(self, text: str) -> Optional[str]:
        """Extract document type from OCR text."""
        text_lower = text.lower()
        
        for doc_type in self.document_types:
            if doc_type in text_lower:
                return doc_type.upper()
        
        # Look for additional patterns
        if 'explanation of benefits' in text_lower:
            return 'EOB'
        elif 'summary of benefits' in text_lower:
            return 'SUMMARY'
        elif any(word in text_lower for word in ['payment', 'remittance']):
            return 'PAYMENT'
        
        return None
    
    def generate_filename(self, image_path: Path, text: str) -> str:
        """Generate new filename based on extracted information."""
        # Extract all components
        patient_name = self.extract_patient_name(text)
        date_str = self.extract_date(text)
        bill_amount = self.extract_bill_amount(text)
        hospital_name = self.extract_hospital_name(text)
        provider = self.extract_provider(text)
        doc_type = self.extract_document_type(text)
        
        # Build filename components in order: Date_PatientName_Hospital_Amount_Provider_DocType
        filename_parts = []
        
        # Add date (use current date if not found)
        if date_str:
            filename_parts.append(date_str)
        else:
            filename_parts.append(datetime.now().strftime(self.date_format))
        
        # Add patient name
        if patient_name:
            # Clean patient name for filename
            clean_name = re.sub(r'[^a-zA-Z\s]', '', patient_name)
            clean_name = re.sub(r'\s+', '', clean_name)  # Remove spaces
            filename_parts.append(clean_name)
        else:
            filename_parts.append('UnknownPatient')
        
        # Add hospital/billing entity
        if hospital_name:
            # Clean hospital name for filename
            clean_hospital = re.sub(r'[^a-zA-Z\s]', '', hospital_name)
            clean_hospital = re.sub(r'\s+', '', clean_hospital)  # Remove spaces
            # Truncate if too long
            if len(clean_hospital) > 30:
                clean_hospital = clean_hospital[:30]
            filename_parts.append(clean_hospital)
        else:
            filename_parts.append('UnknownHospital')
        
        # Add bill amount
        if bill_amount:
            # Clean amount for filename (remove $ and .)
            clean_amount = re.sub(r'[^0-9]', '', bill_amount)
            filename_parts.append(f"{clean_amount}USD")
        else:
            filename_parts.append('UnknownAmount')
        
        # Add provider (optional)
        if provider:
            filename_parts.append(provider.replace(' ', ''))
        
        # Add document type (optional)
        if doc_type:
            filename_parts.append(doc_type)
        
        # Create base filename
        base_filename = '_'.join(filename_parts)
        
        # Sanitize filename (remove any remaining special characters)
        base_filename = re.sub(r'[^a-zA-Z0-9_-]', '', base_filename)
        
        # Truncate if too long
        if len(base_filename) > self.max_filename_length - 10:  # Leave space for extension
            base_filename = base_filename[:self.max_filename_length - 10]
        
        # Add original extension
        extension = image_path.suffix.lower()
        new_filename = f"{base_filename}{extension}"
        
        # Handle duplicates
        counter = 1
        final_path = self.output_dir / new_filename
        while final_path.exists():
            name_without_ext = base_filename
            new_filename = f"{name_without_ext}_{counter:02d}{extension}"
            final_path = self.output_dir / new_filename
            counter += 1
        
        return new_filename
    
    def process_image(self, image_path: Path) -> bool:
        """Process a single image file."""
        try:
            logger.info(f"Processing: {image_path.name}")
            
            # Extract text from image
            text = self.extract_text(image_path)
            if not text:
                logger.warning(f"No text extracted from {image_path.name}")
                # Use fallback naming
                timestamp = datetime.now().strftime(self.date_format)
                new_filename = f"{timestamp}_Unknown_Document{image_path.suffix}"
            else:
                logger.debug(f"Extracted text (first 100 chars): {text[:100]}...")
                new_filename = self.generate_filename(image_path, text)
            
            # Copy file with new name
            output_path = self.output_dir / new_filename
            shutil.copy2(image_path, output_path)
            
            logger.success(f"Renamed: {image_path.name} -> {new_filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process {image_path.name}: {e}")
            return False
    
    def process_directory(self) -> Tuple[int, int]:
        """Process all images in the input directory."""
        # Supported image extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.pdf'}
        
        # Find all image files
        image_files = []
        for ext in image_extensions:
            image_files.extend(self.input_dir.glob(f"*{ext}"))
            image_files.extend(self.input_dir.glob(f"*{ext.upper()}"))
        
        if not image_files:
            logger.warning(f"No image files found in {self.input_dir}")
            return 0, 0
        
        logger.info(f"Found {len(image_files)} image files to process")
        
        # Process each image
        successful = 0
        failed = 0
        
        for image_path in image_files:
            if self.process_image(image_path):
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Processing complete: {successful} successful, {failed} failed")
        return successful, failed


def main():
    """Main entry point."""
    logger.add("image_renamer.log", rotation="10 MB", retention="7 days")
    
    try:
        renamer = MedicalImageRenamer()
        successful, failed = renamer.process_directory()
        
        print(f"\n✅ Processing complete!")
        print(f"Successfully processed: {successful} files")
        if failed > 0:
            print(f"Failed to process: {failed} files")
        print(f"Output directory: {renamer.output_dir}")
        
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        print("\n⏹️  Processing interrupted")
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
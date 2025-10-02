# Medical Billing Image Renamer

Automatically renames medical billing images based on OCR-extracted content to generate meaningful filenames with provider, date, and document type information.

## Features

- **OCR Text Extraction**: Uses Tesseract OCR to extract text from images
- **Smart Filename Generation**: Creates descriptive filenames using:
  - Patient name extraction
  - Date of service extraction (multiple formats supported)
  - Bill amount detection
  - Hospital/billing entity identification
  - Insurance provider detection (Cigna, Aetna, BCBS, etc.)
  - Document type identification (EOB, Claims, Statements, etc.)
- **Image Preprocessing**: Enhances images for better OCR accuracy
- **Duplicate Handling**: Automatically handles filename conflicts
- **Configurable**: Customizable via environment variables

## Installation

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Tesseract OCR**:
   - **macOS**: `brew install tesseract`
   - **Ubuntu**: `sudo apt install tesseract-ocr`
   - **Windows**: Download from [GitHub releases](https://github.com/UB-Mannheim/tesseract/wiki)

3. **Configure settings** (optional):
   Edit `.env` file to customize directories and detection keywords.

## Usage

1. **Place images** in the `input_images` directory (created automatically)

2. **Run the renamer**:
   ```bash
   python image_renamer.py
   ```

3. **Find renamed files** in the `output_images` directory

## Example Output

Input: `IMG_001.jpg` (contains medical bill for John Doe from General Hospital, $450.75, dated 12/15/2023)  
Output: `20231215_JohnDoe_GeneralHospital_45075USD_Cigna_EOB.jpg`

Input: `scan.png` (contains Aetna claim for Jane Smith from City Clinic, $125.00, dated Jan 5, 2024)  
Output: `20240105_JaneSmith_CityClinic_12500USD_Aetna_CLAIM.png`

## Configuration

Edit `.env` file to customize:

- `INPUT_DIR`: Directory containing images to rename
- `OUTPUT_DIR`: Directory for renamed images  
- `TESSERACT_CMD`: Path to tesseract executable
- `PROVIDER_KEYWORDS`: Comma-separated list of insurance providers
- `DOCUMENT_TYPES`: Comma-separated list of document types
- `PATIENT_KEYWORDS`: Keywords for patient name detection
- `HOSPITAL_KEYWORDS`: Keywords for hospital/provider detection
- `AMOUNT_KEYWORDS`: Keywords for bill amount detection
- `OCR_CONFIDENCE_THRESHOLD`: Minimum OCR confidence (0-100)
- `MAX_FILENAME_LENGTH`: Maximum filename length (default: 150)

## Supported Formats

- Images: JPG, PNG, TIFF, BMP
- Documents: PDF (experimental)

## Logging

- Console output shows processing progress
- Detailed logs saved to `image_renamer.log`
- Log rotation: 10MB files, 7-day retention


# Cigna International AI Claim Filing Agent

An intelligent automation system that processes medical bills from WhatsApp, extracts relevant data using OCR and AI, and automatically submits insurance claims to Cigna International's portal.

## Features

- 📱 **WhatsApp Integration**: Receive scanned medical bills via WhatsApp
- 🔍 **Smart OCR + AI Extraction**: Extract provider, patient, dates, amounts, and diagnosis codes
- 🤖 **Automated Claim Submission**: Submit claims to Cigna International website automatically
- 📊 **Status Tracking**: Monitor claim progress and settlement amounts
- 📈 **CSV Exports**: Export claim data for Google Sheets or Excel analysis
- 🔒 **Secure**: All credentials stored securely in environment variables
- ⚡ **Async Processing**: Handle multiple claims concurrently with rate limiting

## Architecture

```
WhatsApp → OCR/AI Extraction → Cigna Web Automation → Status Tracking → CSV Export
    ↓              ↓                    ↓                   ↓            ↓
 Images       Structured Data      Claim Numbers      Updates     Google Sheets
```

## Quick Start

### 1. Setup Environment

```bash
# Clone repository
git clone <repository-url>
cd cigna-AI-agent-v1

# Run setup script
python setup.py
```

### 2. Configure Credentials

Edit `.env` file with your credentials:

```env
# OpenAI for document processing
OPENAI_API_KEY=your_openai_api_key_here

# Twilio for WhatsApp integration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890

# Cigna International portal credentials
CIGNA_USERNAME=your_cigna_username
CIGNA_PASSWORD=your_cigna_password
```

### 3. Install Dependencies

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install Tesseract for OCR
# macOS
brew install tesseract

# Ubuntu/Debian  
sudo apt install tesseract-ocr

# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
```

### 4. Test Installation

```bash
python scripts/test_components.py
```

### 5. Run the Agent

```bash
python main.py
```

## Usage

### Submitting Claims via WhatsApp

1. Send a photo of your medical bill to the configured WhatsApp number
2. The agent will:
   - Extract bill information using OCR + AI
   - Send you a confirmation with extracted details
   - Submit the claim to Cigna automatically
   - Track status and send updates

### Monitoring Claims

- **CSV Export**: Check `data/exports/cigna_claims_latest.csv`
- **Google Sheets**: Import the CSV for real-time dashboard
- **Logs**: Monitor `logs/cigna_agent.log` for detailed activity

### Example WhatsApp Interaction

```
You: [sends photo of medical bill]

Agent: ✅ Medical bill received and processed!

📋 Claim ID: 123
🏥 Provider: General Hospital
👤 Patient: John Doe  
📅 Service Date: 2024-01-15
💰 Amount: 225.00 USD
🩺 Treatment: Medical consultation

I'll now submit this claim to Cigna International automatically.

Agent: 📤 Claim Update
📋 Claim ID: 123
📊 Status: SUBMITTED
🔢 Cigna Claim #: CL240115001
```

## Project Structure

```
cigna-AI-agent-v1/
├── src/
│   ├── config/           # Settings and configuration
│   ├── database/         # SQLite database models
│   ├── whatsapp/         # WhatsApp message handling
│   ├── document_processor/ # OCR and AI extraction
│   ├── cigna_automation/ # Web automation for Cigna
│   └── utils/           # Logging, error handling, exports
├── data/
│   ├── uploads/         # Medical bill images
│   ├── exports/         # CSV export files
│   └── claims.db        # SQLite database
├── logs/                # Application logs
├── scripts/            # Setup and testing scripts
├── main.py             # Application entry point
└── requirements.txt    # Python dependencies
```

## Configuration Options

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for document processing | Yes |
| `TWILIO_ACCOUNT_SID` | Twilio account ID | Yes |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | Yes |
| `TWILIO_WHATSAPP_NUMBER` | Your Twilio WhatsApp number | Yes |
| `CIGNA_USERNAME` | Cigna portal username | Yes |
| `CIGNA_PASSWORD` | Cigna portal password | Yes |
| `MAX_CONCURRENT_CLAIMS` | Max parallel claims (default: 3) | No |
| `CLAIM_CHECK_INTERVAL` | Status check interval in seconds (default: 3600) | No |

### Advanced Settings

- **Database Path**: Customize with `DATABASE_PATH`
- **Upload Directory**: Customize with `UPLOAD_DIR`  
- **Export Directory**: Customize with `EXPORT_DIR`
- **Tesseract Path**: Set `TESSERACT_PATH` if not in system PATH

## CSV Export Format

The system exports claims data in multiple formats:

### Main Export (`cigna_claims_latest.csv`)
- Complete claim details with all extracted fields
- Processing times and status history
- Settlement amounts and currencies

### Google Sheets Format (`cigna_claims_google_sheets.csv`)
- Simplified view optimized for spreadsheet viewing
- Key metrics like days pending and status summaries

### Summary Report (`cigna_claims_summary_latest.csv`) 
- Aggregate statistics and success rates
- Count by status and average processing times

## Troubleshooting

### Common Issues

**"OCR extraction failed"**
- Ensure Tesseract is installed and in PATH
- Check image quality - text should be clear and readable
- Verify `TESSERACT_PATH` environment variable if needed

**"Login failed"**  
- Verify Cigna credentials in `.env`
- Check if Cigna changed their login page structure
- Monitor `logs/cigna_automation.log` for details

**"WhatsApp webhook not receiving messages"**
- Verify Twilio configuration and webhook URL
- Check Twilio console for delivery status
- Ensure WhatsApp number is properly configured

### Log Files

- `logs/cigna_agent.log` - Main application log
- `logs/whatsapp.log` - WhatsApp specific events
- `logs/cigna_automation.log` - Web automation details
- `logs/errors.log` - Error-only log for quick debugging

### Testing

```bash
# Test individual components
python scripts/test_components.py

# Test with sample image
python -c "
import asyncio
from src.document_processor.extractor import DocumentExtractor
from src.config.settings import get_settings

async def test():
    extractor = DocumentExtractor(get_settings())
    # Add your test image path here
    result = await extractor.extract_bill_data('path/to/test/bill.jpg')
    print(result)

asyncio.run(test())
"
```

## Security Considerations

- All credentials are stored in environment variables
- Database contains no sensitive authentication data
- Medical images are stored locally only
- Web automation uses secure browser contexts
- Logs do not contain sensitive information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

Private project - All rights reserved

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review log files in `logs/` directory
3. Test individual components with `scripts/test_components.py`
4. Open an issue with detailed error messages and logs
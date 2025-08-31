#!/usr/bin/env python3

import subprocess
import sys
import os
from pathlib import Path


def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Command: {command}")
        print(f"   Error: {e.stderr}")
        return False


def setup_environment():
    """Set up the development environment"""
    print("🚀 Setting up Cigna AI Agent environment...\n")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version.split()[0]} detected")
    
    # Create virtual environment if it doesn't exist
    if not Path("venv").exists():
        if not run_command("python -m venv venv", "Creating virtual environment"):
            sys.exit(1)
    
    # Determine activation command based on OS
    if os.name == 'nt':  # Windows
        activate_cmd = "venv\\Scripts\\activate"
        pip_cmd = "venv\\Scripts\\pip"
    else:  # Unix/macOS
        activate_cmd = "source venv/bin/activate"
        pip_cmd = "venv/bin/pip"
    
    # Install requirements
    if not run_command(f"{pip_cmd} install -r requirements.txt", "Installing Python dependencies"):
        sys.exit(1)
    
    # Install Playwright browsers
    playwright_cmd = "venv/bin/playwright" if os.name != 'nt' else "venv\\Scripts\\playwright"
    if not run_command(f"{playwright_cmd} install", "Installing Playwright browsers"):
        print("⚠️  Playwright browser installation failed. You may need to install manually.")
    
    # Create necessary directories
    directories = ["data", "data/uploads", "data/exports", "logs"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    print("✅ Created data directories")
    
    # Copy environment template
    if not Path(".env").exists():
        if Path(".env.example").exists():
            import shutil
            shutil.copy(".env.example", ".env")
            print("✅ Created .env file from template")
        else:
            print("⚠️  No .env.example found. Please create .env manually.")
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your credentials:")
    print("   - OpenAI API key")
    print("   - Twilio WhatsApp credentials") 
    print("   - Cigna login credentials")
    print("2. Test OCR by installing Tesseract:")
    print("   - macOS: brew install tesseract")
    print("   - Ubuntu: apt install tesseract-ocr")
    print("   - Windows: Download from GitHub")
    print("3. Run the agent: python main.py")


if __name__ == "__main__":
    setup_environment()
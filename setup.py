#!/usr/bin/env python3
"""
Setup script for SalesOps AI Assistant
Helps with initial project configuration
"""

import os
import sys
from pathlib import Path

def create_directory_structure():
    """Create necessary directories"""
    directories = [
        'agents',
        'schema',
        'tools',
        'logs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        init_file = Path(directory) / '__init__.py'
        if not init_file.exists():
            init_file.touch()
    
    print("✅ Directory structure created")

def check_env_file():
    """Check if .env file exists"""
    if not Path('.env').exists():
        if Path('.env.example').exists():
            print("⚠️  .env file not found")
            print("Creating .env from .env.example...")
            with open('.env.example', 'r') as src, open('.env', 'w') as dst:
                dst.write(src.read())
            print("✅ .env file created - please update with your credentials")
        else:
            print("❌ .env.example not found")
    else:
        print("✅ .env file exists")

def check_service_account():
    """Check if service account file exists"""
    if not Path('service_account.json').exists():
        print("⚠️  service_account.json not found")
        print("Please download your Google Service Account JSON and save as 'service_account.json'")
        print("Instructions: https://cloud.google.com/iam/docs/creating-managing-service-account-keys")
    else:
        print("✅ service_account.json found")

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import streamlit
        import google.adk
        import gspread
        print("✅ Core dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def main():
    """Main setup function"""
    print("🚀 SalesOps AI Assistant - Setup Script")
    print("=" * 50)
    
    create_directory_structure()
    check_env_file()
    check_service_account()
    
    if check_dependencies():
        print("\n" + "=" * 50)
        print("✅ Setup complete!")
        print("\nNext steps:")
        print("1. Update .env with your GOOGLE_API_KEY")
        print("2. Add service_account.json file")
        print("3. Create Google Sheet and share with service account")
        print("4. Run: streamlit run app.py")
    else:
        print("\n" + "=" * 50)
        print("⚠️  Please install dependencies first:")
        print("   pip install -r requirements.txt")

if __name__ == "__main__":
    main()
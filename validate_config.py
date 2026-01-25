#!/usr/bin/env python3
"""
Configuration Validation Script for SalesOps AI Assistant
Checks all required configurations before deployment
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def check_python_version():
    """Check Python version"""
    print_header("Python Version Check")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    if version >= (3, 9):
        print_success(f"Python version: {version_str}")
        return True
    else:
        print_error(f"Python {version_str} detected. Python 3.9+ required")
        return False

def check_env_file():
    """Check .env file configuration"""
    print_header("Environment Configuration Check")
    
    if not Path('.env').exists():
        print_error(".env file not found")
        print_info("Create .env file from .env.example")
        return False
    
    print_success(".env file exists")
    
    load_dotenv()
    
    # Check GOOGLE_API_KEY
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key or api_key == 'your_gemini_api_key':
        print_error("GOOGLE_API_KEY not configured in .env")
        print_info("Get your API key from: https://makersuite.google.com/app/apikey")
        return False
    else:
        # Mask the key for security
        masked_key = f"{api_key[:10]}...{api_key[-5:]}" if len(api_key) > 15 else "***"
        print_success(f"GOOGLE_API_KEY configured: {masked_key}")
    
    # Check CRM_SHEET_NAME
    sheet_name = os.getenv('CRM_SHEET_NAME')
    if sheet_name:
        print_success(f"CRM_SHEET_NAME configured: {sheet_name}")
    else:
        print_warning("CRM_SHEET_NAME not set, using default: Sales_CRM_Production")
    
    return True

def check_service_account():
    """Check service account configuration"""
    print_header("Google Service Account Check")
    
    service_account_path = Path('service_account.json')
    
    if not service_account_path.exists():
        print_warning("service_account.json not found")
        print_info("CRM features will be disabled")
        print_info("To enable CRM:")
        print_info("1. Create service account at: https://console.cloud.google.com/")
        print_info("2. Download JSON key")
        print_info("3. Save as 'service_account.json' in project root")
        return False
    
    print_success("service_account.json exists")
    
    # Validate JSON structure
    try:
        with open(service_account_path, 'r') as f:
            sa_data = json.load(f)
        
        required_fields = [
            'type', 'project_id', 'private_key_id', 'private_key',
            'client_email', 'client_id', 'auth_uri', 'token_uri'
        ]
        
        missing_fields = [field for field in required_fields if field not in sa_data]
        
        if missing_fields:
            print_error(f"Invalid service account JSON. Missing fields: {', '.join(missing_fields)}")
            return False
        
        print_success(f"Project ID: {sa_data.get('project_id')}")
        print_success(f"Service Account: {sa_data.get('client_email')}")
        
        return True
        
    except json.JSONDecodeError:
        print_error("service_account.json is not valid JSON")
        return False
    except Exception as e:
        print_error(f"Error reading service account: {str(e)}")
        return False

def check_dependencies():
    """Check if required packages are installed"""
    print_header("Dependencies Check")
    
    required_packages = {
        'streamlit': 'Streamlit',
        'google.adk': 'Google ADK',
        'gspread': 'GSpread',
        'dotenv': 'Python-dotenv',
        'pydantic': 'Pydantic'
    }
    
    all_installed = True
    
    for package, name in required_packages.items():
        try:
            __import__(package)
            print_success(f"{name} installed")
        except ImportError:
            print_error(f"{name} not installed")
            all_installed = False
    
    if not all_installed:
        print_info("Install dependencies with: pip install -r requirements.txt")
    
    return all_installed

def check_directory_structure():
    """Check if required directories exist"""
    print_header("Directory Structure Check")
    
    required_dirs = ['agents', 'schema', 'tools']
    all_exist = True
    
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists() and dir_path.is_dir():
            print_success(f"{dir_name}/ directory exists")
            
            # Check for __init__.py
            init_file = dir_path / '__init__.py'
            if init_file.exists():
                print_success(f"  {dir_name}/__init__.py exists")
            else:
                print_warning(f"  {dir_name}/__init__.py missing")
                # Create it
                init_file.touch()
                print_info(f"  Created {dir_name}/__init__.py")
        else:
            print_error(f"{dir_name}/ directory missing")
            all_exist = False
    
    return all_exist

def test_google_sheets_connection():
    """Test Google Sheets connection"""
    print_header("Google Sheets Connection Test")
    
    if not Path('service_account.json').exists():
        print_warning("Skipping - service_account.json not found")
        return False
    
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file('service_account.json', scopes=scopes)
        client = gspread.authorize(creds)
        
        print_success("Successfully authenticated with Google Sheets API")
        
        # Try to list spreadsheets (this will verify permissions)
        try:
            sheet_name = os.getenv('CRM_SHEET_NAME', 'Sales_CRM_Production')
            sheet = client.open(sheet_name)
            print_success(f"Successfully accessed sheet: {sheet_name}")
            print_info(f"Sheet URL: {sheet.url}")
            return True
        except gspread.SpreadsheetNotFound:
            print_warning(f"Sheet '{sheet_name}' not found or not shared")
            print_info("Create the sheet and share it with the service account email")
            return False
            
    except Exception as e:
        print_error(f"Google Sheets connection failed: {str(e)}")
        return False

def test_api_key():
    """Test Google AI API key"""
    print_header("Google AI API Test")
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key or api_key == 'your_gemini_api_key':
        print_warning("Skipping - GOOGLE_API_KEY not configured")
        return False
    
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        
        # Try a simple model list
        models = genai.list_models()
        print_success("Google AI API key is valid")
        print_info(f"Available models: {len(list(models))}")
        return True
        
    except Exception as e:
        print_error(f"API key test failed: {str(e)}")
        print_info("Check your API key at: https://makersuite.google.com/app/apikey")
        return False

def generate_report(results):
    """Generate final validation report"""
    print_header("Validation Summary")
    
    total_checks = len(results)
    passed_checks = sum(1 for r in results.values() if r)
    failed_checks = total_checks - passed_checks
    
    print(f"\nTotal Checks: {total_checks}")
    print_success(f"Passed: {passed_checks}")
    
    if failed_checks > 0:
        print_error(f"Failed: {failed_checks}")
    
    print(f"\n{Colors.BOLD}Status by Component:{Colors.END}\n")
    
    for check_name, status in results.items():
        status_icon = "✅" if status else "❌"
        status_text = "PASS" if status else "FAIL"
        color = Colors.GREEN if status else Colors.RED
        print(f"  {status_icon} {check_name:.<40} {color}{status_text}{Colors.END}")
    
    print("\n" + "="*60)
    
    if all(results.values()):
        print_success("\n🎉 All checks passed! System is ready to deploy.\n")
        return True
    else:
        print_warning("\n⚠️  Some checks failed. Please fix the issues above.\n")
        return False

def main():
    """Main validation function"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                                                            ║")
    print("║          SalesOps AI Assistant - Config Validator          ║")
    print("║                                                            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")
    
    results = {}
    
    # Run all checks
    results['Python Version'] = check_python_version()
    results['Environment File'] = check_env_file()
    results['Service Account'] = check_service_account()
    results['Dependencies'] = check_dependencies()
    results['Directory Structure'] = check_directory_structure()
    
    # Optional tests (don't fail overall validation)
    if results['Environment File']:
        test_api_key()  # Informational only
    
    if results['Service Account']:
        test_google_sheets_connection()  # Informational only
    
    # Generate report
    success = generate_report(results)
    
    if success:
        print_info("Next steps:")
        print_info("  1. Run: streamlit run app.py")
        print_info("  2. Open http://localhost:8501 in your browser")
        print_info("  3. Test with sample_transcript.txt")
        return 0
    else:
        print_info("Next steps:")
        print_info("  1. Fix the failed checks above")
        print_info("  2. Run this validator again")
        print_info("  3. Check README.md for detailed setup instructions")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Validation cancelled by user{Colors.END}\n")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {str(e)}{Colors.END}\n")
        sys.exit(1)
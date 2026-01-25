#!/bin/bash

# SalesOps AI Assistant - Quick Start Script

echo "🚀 SalesOps AI Assistant - Starting..."
echo "======================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.9 or higher."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

# Install/upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install dependencies
if [ -f "requirements.txt" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt > /dev/null 2>&1
    echo "✅ Dependencies installed"
else
    echo "❌ requirements.txt not found"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Created .env from template - please update with your credentials"
        echo "❌ Cannot start without valid configuration"
        exit 1
    fi
fi

# Check for service account
if [ ! -f "service_account.json" ]; then
    echo "⚠️  service_account.json not found - CRM features will be disabled"
fi

# Run the application
echo ""
echo "======================================"
echo "🚀 Starting Streamlit application..."
echo "======================================"
echo ""

streamlit run app.py
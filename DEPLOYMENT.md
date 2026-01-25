# 🚀 Deployment Guide - SalesOps AI Assistant

This guide covers deploying the SalesOps AI Assistant to various production environments.

## Table of Contents

1. [Streamlit Cloud (Recommended for Demo)](#streamlit-cloud)
2. [Google Cloud Run](#google-cloud-run)
3. [AWS EC2](#aws-ec2)
4. [Heroku](#heroku)
5. [Docker Deployment](#docker-deployment)

---

## Streamlit Cloud

**Best for:** Quick demos, MVP, non-production testing

### Prerequisites
- GitHub account
- Streamlit Cloud account (free tier available)
- Google Cloud credentials

### Steps

1. **Push Code to GitHub**

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

2. **Prepare Secrets**

Do NOT commit these files:
- `.env`
- `service_account.json`

3. **Deploy to Streamlit Cloud**

- Go to [share.streamlit.io](https://share.streamlit.io)
- Click "New app"
- Select your repository
- Set main file: `app.py`
- Click "Advanced settings"

4. **Configure Secrets**

In the Streamlit Cloud secrets section, add:

```toml
GOOGLE_API_KEY = "your_actual_api_key_here"
CRM_SHEET_NAME = "Sales_CRM_Production"

[service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nYour-Key-Here\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your-cert-url"
```

5. **Update Code for Streamlit Cloud**

Modify `tools/google_sheets_crm.py`:

```python
import streamlit as st
import json

def get_credentials():
    """Get credentials from Streamlit secrets or local file"""
    try:
        # Try Streamlit Cloud secrets first
        if 'service_account' in st.secrets:
            return Credentials.from_service_account_info(
                st.secrets["service_account"],
                scopes=scopes
            )
    except:
        pass
    
    # Fall back to local file
    return Credentials.from_service_account_file(
        "service_account.json",
        scopes=scopes
    )
```

6. **Deploy**

Click "Deploy" and wait for the build to complete.

---

## Google Cloud Run

**Best for:** Production, scalable deployments, enterprise use

### Prerequisites
- Google Cloud account with billing enabled
- `gcloud` CLI installed
- Docker installed

### Steps

1. **Create Dockerfile**

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
```

2. **Create `.dockerignore`**

```
venv/
__pycache__/
*.pyc
.env
service_account.json
.git/
```

3. **Build and Push to Google Container Registry**

```bash
# Set your project ID
PROJECT_ID="your-gcp-project-id"
IMAGE_NAME="salesops-ai"

# Build the image
docker build -t gcr.io/$PROJECT_ID/$IMAGE_NAME .

# Configure Docker for GCR
gcloud auth configure-docker

# Push to GCR
docker push gcr.io/$PROJECT_ID/$IMAGE_NAME
```

4. **Deploy to Cloud Run**

```bash
gcloud run deploy salesops-ai \
  --image gcr.io/$PROJECT_ID/$IMAGE_NAME \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY="your-key" \
  --set-env-vars CRM_SHEET_NAME="Sales_CRM_Production"
```

5. **Add Service Account Secret**

```bash
# Create secret from file
gcloud secrets create service-account-key \
  --data-file=service_account.json

# Grant access to Cloud Run
gcloud secrets add-iam-policy-binding service-account-key \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

6. **Update Code to Use Secrets**

```python
import google.cloud.secretmanager as sm

def get_service_account_from_secret():
    client = sm.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/service-account-key/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return json.loads(response.payload.data.decode("UTF-8"))
```

---

## AWS EC2

**Best for:** Full control, custom configurations

### Steps

1. **Launch EC2 Instance**

- AMI: Ubuntu 22.04 LTS
- Instance type: t3.medium (recommended)
- Security group: Allow ports 22, 80, 8501

2. **Connect and Setup**

```bash
ssh -i your-key.pem ubuntu@your-ec2-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3-pip python3-venv -y

# Clone repository
git clone <your-repo-url>
cd salesops-ai-assistant
```

3. **Install Dependencies**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. **Configure Environment**

```bash
nano .env
# Add your credentials

# Upload service account
scp -i your-key.pem service_account.json ubuntu@your-ec2-ip:~/salesops-ai-assistant/
```

5. **Run with systemd (Production)**

Create `/etc/systemd/system/salesops-ai.service`:

```ini
[Unit]
Description=SalesOps AI Assistant
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/salesops-ai-assistant
Environment="PATH=/home/ubuntu/salesops-ai-assistant/venv/bin"
ExecStart=/home/ubuntu/salesops-ai-assistant/venv/bin/streamlit run app.py --server.port=8501

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable salesops-ai
sudo systemctl start salesops-ai
sudo systemctl status salesops-ai
```

6. **Setup Nginx Reverse Proxy**

```bash
sudo apt install nginx -y

# Create nginx config
sudo nano /etc/nginx/sites-available/salesops-ai
```

Add:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/salesops-ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Heroku

**Best for:** Simple deployments, managed infrastructure

### Steps

1. **Create `Procfile`**

```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

2. **Create `setup.sh`**

```bash
mkdir -p ~/.streamlit/

echo "\
[server]\n\
headless = true\n\
port = $PORT\n\
enableCORS = false\n\
\n\
" > ~/.streamlit/config.toml
```

3. **Deploy**

```bash
# Login to Heroku
heroku login

# Create app
heroku create your-app-name

# Set environment variables
heroku config:set GOOGLE_API_KEY="your-key"
heroku config:set CRM_SHEET_NAME="Sales_CRM_Production"

# Add service account (as base64)
cat service_account.json | base64 | heroku config:set SERVICE_ACCOUNT_JSON_BASE64=

# Deploy
git push heroku main
```

4. **Update Code to Decode Service Account**

```python
import base64
import os

service_account_b64 = os.getenv('SERVICE_ACCOUNT_JSON_BASE64')
if service_account_b64:
    sa_json = base64.b64decode(service_account_b64).decode()
    sa_dict = json.loads(sa_json)
    creds = Credentials.from_service_account_info(sa_dict, scopes=scopes)
```

---

## Docker Deployment

**Best for:** Consistent environments, Kubernetes, local testing

### Complete Docker Setup

1. **Dockerfile** (optimized)

```dockerfile
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

2. **docker-compose.yml**

```yaml
version: '3.8'

services:
  salesops-ai:
    build: .
    ports:
      - "8501:8501"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - CRM_SHEET_NAME=${CRM_SHEET_NAME}
    volumes:
      - ./service_account.json:/app/service_account.json:ro
    restart: unless-stopped
```

3. **Build and Run**

```bash
# Build image
docker build -t salesops-ai:latest .

# Run container
docker run -p 8501:8501 \
  -e GOOGLE_API_KEY="your-key" \
  -e CRM_SHEET_NAME="Sales_CRM_Production" \
  -v $(pwd)/service_account.json:/app/service_account.json:ro \
  salesops-ai:latest

# Or use docker-compose
docker-compose up -d
```

---

## Security Best Practices

### 1. Environment Variables
- Never commit `.env` or `service_account.json`
- Use platform-specific secret management
- Rotate keys regularly

### 2. HTTPS
- Always use SSL/TLS in production
- Use Let's Encrypt for free certificates
- Configure HSTS headers

### 3. Access Control
- Implement authentication (Streamlit auth, OAuth)
- Use VPN for internal deployments
- Restrict API access by IP

### 4. Monitoring
- Set up logging (CloudWatch, Stackdriver)
- Configure alerts for errors
- Monitor resource usage

### 5. Backups
- Regular database backups
- Version control for configuration
- Disaster recovery plan

---

## Performance Optimization

### 1. Caching
```python
@st.cache_data
def load_data():
    # Cache expensive operations
    pass
```

### 2. Connection Pooling
```python
@st.cache_resource
def get_sheets_client():
    # Reuse connections
    return client
```

### 3. Async Processing
```python
# Use background jobs for long tasks
import asyncio
```

---

## Troubleshooting

### Common Issues

**Port Already in Use**
```bash
# Find and kill process
lsof -ti:8501 | xargs kill -9
```

**Permission Denied**
```bash
# Fix file permissions
chmod +x run.sh
```

**Out of Memory**
```bash
# Increase swap (Linux)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## Cost Estimation

### Streamlit Cloud
- Free tier: 1 app
- Paid: $20/month per app

### Google Cloud Run
- Free tier: 2M requests/month
- Typical: $10-50/month

### AWS EC2
- t3.medium: ~$30/month
- + bandwidth costs

### Heroku
- Hobby tier: $7/month
- Production: $25-50/month

---

## Next Steps

After deployment:
1. Set up monitoring and alerts
2. Configure automated backups
3. Implement CI/CD pipeline
4. Load testing
5. Security audit
6. User documentation

---

**Need Help?**
- Check logs: `streamlit run app.py --logger.level=debug`
- Community: Streamlit Forum, Stack Overflow
- Issues: GitHub Issues
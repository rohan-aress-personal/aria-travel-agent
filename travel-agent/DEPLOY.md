# 🐳 Docker + Azure Container Apps — Deployment Guide
# Resource Group : Azure_Learning_RZ
# Registry       : ariatravelacr
# Container App  : aria-travel-app

---

## Prerequisites

- Docker Desktop installed and running
- Azure CLI — install from https://aka.ms/installazurecli
- Logged in: `az login`

---

## Step 1 — Build & Test Locally

```bash
cd travel-agent

# Build image
docker build -t aria-travel-agent .

# Test locally with your .env
docker run -p 8000:8000 --env-file .env aria-travel-agent
# → open http://localhost:8000
```

---

## Step 2 — Create Azure Container Registry in Azure_Learning_RZ

```bash
# Create ACR inside your existing resource group
az acr create \
  --resource-group Azure_Learning_RZ \
  --name ariatravelacr \
  --sku Basic \
  --admin-enabled true

# Login to ACR
az acr login --name ariatravelacr

# Tag local image for ACR
docker tag aria-travel-agent \
  ariatravelacr.azurecr.io/aria-travel-agent:latest

# Push to ACR
docker push ariatravelacr.azurecr.io/aria-travel-agent:latest

# Verify
az acr repository list --name ariatravelacr --output table
```

---

## Step 3 — Create Container Apps Environment

```bash
# Install extension (first time only)
az extension add --name containerapp --upgrade

# Register required providers (first time only)
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

# Create the Container Apps environment inside Azure_Learning_RZ
az containerapp env create \
  --name aria-travel-env \
  --resource-group Azure_Learning_RZ \
  --location eastus2
```

---

## Step 4 — Store Secrets Securely

Never pass API keys as plain text. Create the app first with a placeholder,
then set secrets:

```bash
# Get ACR password
ACR_PASSWORD=$(az acr credential show \
  --name ariatravelacr \
  --query "passwords[0].value" \
  --output tsv)

# Create the container app (secrets added in next command)
az containerapp create \
  --name aria-travel-app \
  --resource-group Azure_Learning_RZ \
  --environment aria-travel-env \
  --image ariatravelacr.azurecr.io/aria-travel-agent:latest \
  --registry-server ariatravelacr.azurecr.io \
  --registry-username ariatravelacr \
  --registry-password $ACR_PASSWORD \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 1 \
  --cpu 0.5 \
  --memory 1.0Gi

# Add secrets separately (replace values with your actual keys)
az containerapp secret set \
  --name aria-travel-app \
  --resource-group Azure_Learning_RZ \
  --secrets \
    openai-key="YOUR_AZURE_OPENAI_API_KEY" \
    weather-key="YOUR_OPENWEATHER_API_KEY" \
    exchange-key="YOUR_EXCHANGE_RATE_API_KEY" \
    tripmap-key="YOUR_OPENTRIPMAP_API_KEY" \
    storage-conn="YOUR_AZURE_STORAGE_CONNECTION_STRING" \
    email-addr="YOUR_EMAIL_ADDRESS" \
    email-pass="YOUR_EMAIL_APP_PASSWORD"
```

---

## Step 5 — Set Environment Variables (referencing secrets)

```bash
az containerapp update \
  --name aria-travel-app \
  --resource-group Azure_Learning_RZ \
  --set-env-vars \
    AZURE_OPENAI_ENDPOINT="https://visha-mmsqm1vp-eastus2.cognitiveservices.azure.com/" \
    AZURE_OPENAI_API_KEY="secretref:openai-key" \
    AZURE_OPENAI_DEPLOYMENT_NAME="gpt-5.3-chat" \
    AZURE_OPENAI_API_VERSION="2024-12-01-preview" \
    OPENWEATHER_API_KEY="secretref:weather-key" \
    EXCHANGE_RATE_API_KEY="secretref:exchange-key" \
    OPENTRIPMAP_API_KEY="secretref:tripmap-key" \
    AZURE_STORAGE_CONNECTION_STRING="secretref:storage-conn" \
    AZURE_STORAGE_CONTAINER_NAME="travel-images" \
    EMAIL_PROVIDER="gmail" \
    EMAIL_SENDER_ADDRESS="secretref:email-addr" \
    EMAIL_SENDER_PASSWORD="secretref:email-pass"
```

---

## Step 6 — Get Your Live URL

```bash
az containerapp show \
  --name aria-travel-app \
  --resource-group Azure_Learning_RZ \
  --query properties.configuration.ingress.fqdn \
  --output tsv
# → aria-travel-app.<hash>.eastus2.azurecontainerapps.io
```

Open that URL in your browser — Aria is live! 🎉

---

## Redeploy After Code Changes

```bash
# Rebuild and push new image
docker build -t aria-travel-agent .
docker tag aria-travel-agent \
  ariatravelacr.azurecr.io/aria-travel-agent:latest
docker push ariatravelacr.azurecr.io/aria-travel-agent:latest

# Trigger redeployment
az containerapp update \
  --name aria-travel-app \
  --resource-group Azure_Learning_RZ \
  --image ariatravelacr.azurecr.io/aria-travel-agent:latest
```

---

## Useful Commands

```bash
# Stream live logs
az containerapp logs show \
  --name aria-travel-app \
  --resource-group Azure_Learning_RZ \
  --follow

# Check running status
az containerapp show \
  --name aria-travel-app \
  --resource-group Azure_Learning_RZ \
  --query properties.runningStatus \
  --output tsv

# List all resources in your group
az resource list \
  --resource-group Azure_Learning_RZ \
  --output table

# Delete only the container app (keeps everything else in Azure_Learning_RZ)
az containerapp delete \
  --name aria-travel-app \
  --resource-group Azure_Learning_RZ \
  --yes
```

---

## Free Tier Summary

| Resource | What you get free |
|----------|-------------------|
| Container Apps Consumption | 180,000 vCPU-seconds/month |
| Container Apps Consumption | 360,000 GiB-seconds/month |
| ACR Basic | 10 GB image storage |
| min-replicas = 0 | Scales to zero → zero cost when idle |

> With `--min-replicas 0` the container shuts down when nobody uses it
> and cold-starts in ~10s on first request. Perfect for dev/demo workloads.

# Google Cloud Deployment Guide

This guide explains how to deploy the Route Planner app to Google App Engine.

## Prerequisites

1. Google Cloud account (create at https://console.cloud.google.com)
2. Google Cloud SDK installed (https://cloud.google.com/sdk/docs/install)
3. gcloud CLI configured with your project

## Step 1: Set Up Google Cloud Project

```bash
# Set your project ID (replace with your actual project)
gcloud config set project YOUR_PROJECT_ID

# Create a new project (if needed)
gcloud projects create route-planner-app

# Set it as the active project
gcloud config set project route-planner-app
```

## Step 2: Secure Your API Key with Secret Manager

### Option A: Create a secret in Google Cloud (RECOMMENDED)

```bash
# Create a secret for the MapTiler API key
echo "4LTxwIKBMtXtHZkO3INT" | gcloud secrets create maptiler-api-key --data-file=-

# Grant App Engine service account access to the secret
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding maptiler-api-key \
  --member=serviceAccount:$PROJECT_NUMBER@appspot.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

### Option B: Use environment variables directly (not recommended for production)

Edit `app.yaml` and set:
```yaml
env_variables:
  MAPTILER_API_KEY: "4LTxwIKBMtXtHZkO3INT"
```

## Step 3: Deploy to Google App Engine

From your project root directory:

```bash
# Deploy the application
gcloud app deploy

# When prompted, select a region (e.g., us-central1)
# Choose "python312" as the runtime

# View deployment progress
gcloud app logs read -f
```

## Step 4: Open Your App

```bash
# Open the deployed app in your browser
gcloud app browse

# OR view the URL
gcloud app describe --format='value(defaultHostname)'
```

Your app will be available at: `https://YOUR_PROJECT_ID.uc.r.appspot.com/`

## Step 5: Monitor & Manage

```bash
# View logs
gcloud app logs read

# View live logs
gcloud app logs read -f

# Check app status
gcloud app describe

# Scale the app
gcloud app deploy --set-env-vars MIN_INSTANCES=2,MAX_INSTANCES=10
```

## Updating Your App

To update after making changes:

```bash
# Deploy new version (same process)
gcloud app deploy

# Traffic automatically shifts to new version
```

## Troubleshooting

### "Service account doesn't have permission"
- Ensure you granted secret accessor role (Step 2)
- Run: `gcloud secrets add-iam-policy-binding maptiler-api-key ...`

### "MAPTILER_API_KEY not set"
- Verify secret was created: `gcloud secrets list`
- Check service account permissions

### App slow or timing out
- Increase `max_instances` in app.yaml
- Check logs: `gcloud app logs read -f`

### How to delete the app
```bash
gcloud app versions delete VERSION_ID
# OR delete entire app service (requires disabling the app first)
```

## Cost Considerations

- **First 28 hours per day**: Free tier
- **After**: ~$0.05-0.10 per hour depending on traffic
- Use `min_instances: 1` to minimize costs
- Set appropriate `max_instances` to prevent runaway billing

## Reference

- [Google App Engine Docs](https://cloud.google.com/appengine/docs)
- [Secret Manager Docs](https://cloud.google.com/secret-manager/docs)
- [FastAPI on App Engine](https://cloud.google.com/appengine/docs/flexible/python/quickstart)

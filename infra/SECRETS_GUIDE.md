# Chitragupt — GitHub Secrets & Variables Setup Guide

This guide walks you through the one-time configuration needed before the CD pipeline
(`cd.yaml`) can run. Follow the section for your chosen cloud provider.

---

## Step 1 — GitHub Variables (shared, all providers)

Go to **Settings → Secrets and variables → Actions → Variables tab** and add:

| Variable name    | Example value      | Description                              |
|------------------|--------------------|------------------------------------------|
| `CLOUD_PROVIDER` | `gcp`              | `gcp` \| `aws` \| `azure`              |
| `DEPLOY_MODE`    | `serverless`       | `serverless` \| `kubernetes`            |
| `DEPLOY_REGION`  | `us-central1`      | Cloud region (provider-specific format) |

---

## Step 2A — GCP Setup

### 2A-1  Run Terraform

```bash
cd infra/terraform/gcp
cp terraform.tfvars.example terraform.tfvars   # fill in values
terraform init
terraform apply
```

Terraform outputs the values you need for the next step.

### 2A-2  Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → Secrets tab** and add:

| Secret name                    | Where to get it                                      |
|--------------------------------|------------------------------------------------------|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `terraform output workload_identity_provider`      |
| `GCP_SERVICE_ACCOUNT`          | `terraform output cd_service_account`                |
| `GCP_ARTIFACT_REGISTRY`        | `terraform output artifact_registry`                 |
| `DB_PASSWORD`                  | Same value you set in `terraform.tfvars`             |
| `REDIS_URL`                    | `redis://:@$(terraform output -raw redis_host):6379/0` |
| `OPENROUTER_API_KEY`           | Your OpenRouter API key                              |

### 2A-3  GKE (if DEPLOY_MODE=kubernetes)

```bash
# Get cluster credentials
gcloud container clusters get-credentials chitragupt-ENVIRONMENT \
  --region REGION --project PROJECT_ID

# Annotate the K8s ServiceAccount for Workload Identity
kubectl annotate serviceaccount chitragupt \
  --namespace chitragupt \
  iam.gke.io/gcp-service-account=$(terraform output -raw runtime_service_account)
```

---

## Step 2B — AWS Setup

### 2B-1  Bootstrap state backend (one-time)

```bash
# Create S3 bucket and DynamoDB lock table before running Terraform
aws s3api create-bucket --bucket chitragupt-tf-state --region us-east-1
aws dynamodb create-table \
  --table-name chitragupt-tf-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### 2B-2  Run Terraform

```bash
cd infra/terraform/aws
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

### 2B-3  Enable GitHub OIDC provider (one-time per account)

If you don't already have the GitHub OIDC provider in your account:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

Then set `count = 1` in `infra/terraform/aws/main.tf` for the `aws_iam_openid_connect_provider` resource
and use the created provider's ARN in the `aws_iam_role` trust policy data source.

### 2B-4  Add GitHub Secrets

| Secret name         | Where to get it                               |
|---------------------|-----------------------------------------------|
| `AWS_OIDC_ROLE_ARN` | `terraform output cd_role_arn`               |
| `AWS_ECR_REGISTRY`  | `terraform output ecr_registry`              |
| `AWS_REGION`        | Same as `var.aws_region` in Terraform        |
| `DB_PASSWORD`       | Same value you set in `terraform.tfvars`      |
| `OPENROUTER_API_KEY`| Your OpenRouter API key                       |

### 2B-5  ECS Cluster + Task Definitions

The CD pipeline updates an existing ECS service. Bootstrap the cluster and initial task
definitions once:

```bash
# Create cluster
aws ecs create-cluster --cluster-name chitragupt-ENVIRONMENT

# Register initial task definitions (use your ECR image URIs)
aws ecs register-task-definition --cli-input-json file://infra/aws/task-def-ai-orchestration.json
```

> Task definition JSON templates are in `infra/aws/` (create these per your ECS configuration).

---

## Step 2C — Azure Setup

### 2C-1  Create the CD application in Azure AD (one-time)

```bash
# Create App Registration for the CD identity
az ad app create --display-name chitragupt-cd
APP_ID=$(az ad app list --display-name chitragupt-cd --query '[0].appId' -o tsv)
az ad sp create --id $APP_ID
```

### 2C-2  Run Terraform

```bash
cd infra/terraform/azure
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

### 2C-3  Add GitHub Secrets

| Secret name                  | Where to get it                                      |
|------------------------------|------------------------------------------------------|
| `AZURE_CLIENT_ID`            | App Registration Application (client) ID             |
| `AZURE_TENANT_ID`            | Your Azure AD tenant ID                              |
| `AZURE_SUBSCRIPTION_ID`      | Your Azure subscription ID                           |
| `AZURE_CONTAINER_REGISTRY`   | `terraform output container_registry`                |
| `AZURE_RESOURCE_GROUP`       | `chitragupt-ENVIRONMENT`                             |
| `AZURE_CONTAINER_APPS_ENV`   | `terraform output container_apps_environment_id`     |
| `DB_PASSWORD`                | Same value you set in `terraform.tfvars`             |
| `OPENROUTER_API_KEY`         | Your OpenRouter API key                              |

---

## Step 3 — Kubernetes overlay secrets (if DEPLOY_MODE=kubernetes)

The Kustomize overlays in `infra/k8s/overlays/staging/` and `.../production/` read a
`secrets.env` file that is **gitignored**. The CD pipeline writes this file automatically
from GitHub Secrets. To test locally:

```bash
cd infra/k8s/overlays/staging
cp secrets.env.example secrets.env
# Edit secrets.env with real values
kubectl apply -k .
```

---

## Step 4 — Verify

Push to `main` and watch the **Actions** tab. The pipeline runs in this order:

```
CI Gate → Configure → Auth → Build & Push
  → Deploy Staging (serverless or k8s)
  → Smoke Test Staging
  → [approval gate for production]
  → Deploy Production
  → Smoke Test Production
  → Rollback (automatic, if smoke fails)
```

---

## Secret rotation

- **GCP**: Rotate by creating a new Secret Manager version — Cloud Run picks it up on next deployment.
- **AWS**: Rotate via Secrets Manager console or CLI; ECS picks it up on next task launch.
- **Azure**: Rotate the Key Vault secret; Container Apps picks it up on next revision.
- **`OPENROUTER_API_KEY`**: Rotate in the cloud secret store + GitHub Secret simultaneously.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `Error: Unable to get OIDC token` | `id-token: write` permission missing | Check job-level `permissions:` block in `cd.yaml` |
| `Error: 403 Forbidden` on image push | WIF binding not applied | Re-run `terraform apply` and check `workload_identity_pool_provider` |
| `ImagePullBackOff` on K8s | ServiceAccount not annotated | Run `kubectl annotate sa` command from Step 2A-3 / 2B-5 |
| `Connection refused :5432` | DB in private subnet, pod not in same VPC | Check VPC/subnet peering in Terraform outputs |

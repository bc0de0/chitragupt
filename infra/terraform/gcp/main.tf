terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
  # Store state in GCS — bucket must be pre-created outside Terraform
  backend "gcs" {
    bucket = "chitragupt-tf-state"
    prefix = "gcp"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

locals {
  name   = "chitragupt-${var.environment}"
  labels = {
    app         = "chitragupt"
    environment = var.environment
    managed-by  = "terraform"
  }
}

# ── Artifact Registry ─────────────────────────────────────────────────────────
resource "google_artifact_registry_repository" "images" {
  repository_id = "chitragupt"
  location      = var.region
  format        = "DOCKER"
  description   = "Chitragupt container images"
  labels        = local.labels
}

# ── Workload Identity Federation (GitHub Actions → GCP) ──────────────────────
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions Pool"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Actions OIDC"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == '${var.github_org}/${var.github_repo}'"
}

resource "google_service_account" "cd_runner" {
  account_id   = "chitragupt-cd"
  display_name = "Chitragupt CD Service Account"
}

resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.cd_runner.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_org}/${var.github_repo}"
}

# Permissions for CD: push images, deploy Cloud Run
resource "google_project_iam_member" "cd_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.cd_runner.email}"
}

resource "google_project_iam_member" "cd_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cd_runner.email}"
}

resource "google_project_iam_member" "cd_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cd_runner.email}"
}

# ── Runtime Service Account (Cloud Run / GKE pods) ───────────────────────────
resource "google_service_account" "runtime" {
  account_id   = "chitragupt-runtime-${var.environment}"
  display_name = "Chitragupt Runtime (${var.environment})"
}

resource "google_project_iam_member" "runtime_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# ── Cloud SQL — PostgreSQL 15 with pgvector ───────────────────────────────────
resource "google_sql_database_instance" "postgres" {
  name             = "${local.name}-pg"
  database_version = "POSTGRES_15"
  region           = var.region
  deletion_protection = var.environment == "production"

  settings {
    tier              = var.db_tier
    availability_type = var.environment == "production" ? "REGIONAL" : "ZONAL"

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = var.environment == "production"
      start_time                     = "03:00"
      backup_retention_settings {
        retained_backups = var.environment == "production" ? 30 : 7
      }
    }

    database_flags {
      name  = "cloudsql.enable_pgvector"
      value = "on"
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }

    user_labels = local.labels
  }

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

resource "google_sql_database" "chitragupt" {
  name     = "chitragupt"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "chitragupt" {
  name     = "chitragupt"
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}

# ── Redis (Memorystore) ───────────────────────────────────────────────────────
resource "google_redis_instance" "cache" {
  name           = "${local.name}-redis"
  tier           = var.environment == "production" ? "STANDARD_HA" : "BASIC"
  memory_size_gb = var.redis_memory_gb
  region         = var.region

  authorized_network = google_compute_network.vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  redis_version = "REDIS_7_0"
  display_name  = "Chitragupt ${var.environment} cache"
  labels        = local.labels
}

# ── VPC + Private Service Access ─────────────────────────────────────────────
resource "google_compute_network" "vpc" {
  name                    = "${local.name}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  name          = "${local.name}-subnet"
  ip_cidr_range = "10.0.0.0/20"
  region        = var.region
  network       = google_compute_network.vpc.id
}

resource "google_compute_global_address" "private_range" {
  name          = "${local.name}-private-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_range.name]
}

# ── Secret Manager ────────────────────────────────────────────────────────────
resource "google_secret_manager_secret" "db_password" {
  secret_id = "${local.name}-pg-password"
  labels    = local.labels
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = var.db_password
}

resource "google_secret_manager_secret" "openrouter_key" {
  secret_id = "${local.name}-openrouter-key"
  labels    = local.labels
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "openrouter_key" {
  secret      = google_secret_manager_secret.openrouter_key.id
  secret_data = var.openrouter_api_key
}

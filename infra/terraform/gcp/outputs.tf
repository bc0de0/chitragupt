output "artifact_registry" {
  description = "Artifact Registry host — use as GCP_ARTIFACT_REGISTRY secret"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "workload_identity_provider" {
  description = "WIF provider — use as GCP_WORKLOAD_IDENTITY_PROVIDER secret"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "cd_service_account" {
  description = "CD service account email — use as GCP_SERVICE_ACCOUNT secret"
  value       = google_service_account.cd_runner.email
}

output "runtime_service_account" {
  description = "Runtime service account email — annotate K8s ServiceAccount for Workload Identity"
  value       = google_service_account.runtime.email
}

output "database_connection_name" {
  description = "Cloud SQL connection name for Cloud SQL Auth Proxy"
  value       = google_sql_database_instance.postgres.connection_name
}

output "redis_host" {
  description = "Redis host (private IP)"
  value       = google_redis_instance.cache.host
  sensitive   = true
}

output "db_password_secret_name" {
  description = "Secret Manager secret name for DB password"
  value       = google_secret_manager_secret.db_password.name
}

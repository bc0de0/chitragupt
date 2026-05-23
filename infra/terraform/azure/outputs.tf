output "container_registry" {
  description = "ACR login server — use as AZURE_CONTAINER_REGISTRY secret"
  value       = azurerm_container_registry.acr.login_server
}

output "runtime_client_id" {
  description = "Managed identity client ID — use as AZURE_CLIENT_ID in K8s ServiceAccount annotation"
  value       = azurerm_user_assigned_identity.runtime.client_id
}

output "container_apps_environment_id" {
  description = "Container Apps Environment resource ID"
  value       = azurerm_container_app_environment.main.id
}

output "db_fqdn" {
  description = "PostgreSQL Flexible Server FQDN"
  value       = azurerm_postgresql_flexible_server.postgres.fqdn
  sensitive   = true
}

output "redis_hostname" {
  description = "Redis cache hostname"
  value       = azurerm_redis_cache.main.hostname
  sensitive   = true
}

output "key_vault_uri" {
  description = "Key Vault URI for secret references"
  value       = azurerm_key_vault.main.vault_uri
}

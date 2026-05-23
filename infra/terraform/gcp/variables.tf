variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment: staging | production"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be 'staging' or 'production'."
  }
}

variable "github_org" {
  description = "GitHub organisation or user name (for Workload Identity Federation)"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (without org prefix)"
  type        = string
  default     = "chitragupt"
}

variable "db_tier" {
  description = "Cloud SQL machine type"
  type        = string
  default     = "db-g1-small"
}

variable "db_password" {
  description = "PostgreSQL password for the chitragupt user"
  type        = string
  sensitive   = true
}

variable "redis_memory_gb" {
  description = "Redis Memorystore memory size in GB"
  type        = number
  default     = 1
}

variable "openrouter_api_key" {
  description = "OpenRouter API key — stored in Secret Manager"
  type        = string
  sensitive   = true
}

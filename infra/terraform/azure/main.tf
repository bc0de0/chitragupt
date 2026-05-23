terraform {
  required_version = ">= 1.7"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.50"
    }
  }
  backend "azurerm" {
    resource_group_name  = "chitragupt-tf-state"
    storage_account_name = "chitragupt"
    container_name       = "tfstate"
    key                  = "azure.terraform.tfstate"
  }
}

provider "azurerm" {
  subscription_id = var.subscription_id
  features {
    key_vault {
      purge_soft_delete_on_destroy = var.environment != "production"
    }
  }
}

provider "azuread" {}

locals {
  name = "chitragupt-${var.environment}"
  tags = {
    App         = "chitragupt"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ── Resource Group ─────────────────────────────────────────────────────────────
resource "azurerm_resource_group" "main" {
  name     = local.name
  location = var.location
  tags     = local.tags
}

# ── Azure Container Registry ───────────────────────────────────────────────────
resource "azurerm_container_registry" "acr" {
  name                = replace(local.name, "-", "")  # ACR names: alphanumeric only
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.environment == "production" ? "Premium" : "Standard"
  admin_enabled       = false  # use Managed Identity, not admin creds
  tags                = local.tags
}

# ── User-Assigned Managed Identity (runtime) ───────────────────────────────────
resource "azurerm_user_assigned_identity" "runtime" {
  name                = "${local.name}-runtime"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.tags
}

resource "azurerm_role_assignment" "runtime_acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.runtime.principal_id
}

# ── Federated Identity Credential (GitHub Actions → Azure) ────────────────────
data "azuread_application" "cd" {
  # CD application must be pre-created in Azure AD; provide its display name or ID.
  display_name = "chitragupt-cd"
}

resource "azuread_application_federated_identity_credential" "github" {
  application_id = data.azuread_application.cd.id
  display_name   = "github-actions"
  description    = "GitHub Actions OIDC for ${var.github_org}/${var.github_repo}"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
}

resource "azuread_application_federated_identity_credential" "github_tags" {
  application_id = data.azuread_application.cd.id
  display_name   = "github-actions-tags"
  description    = "GitHub Actions OIDC — semver tags"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_org}/${var.github_repo}:ref:refs/tags/*"
}

# ── Role assignments for CD identity ──────────────────────────────────────────
data "azuread_service_principal" "cd" {
  display_name = "chitragupt-cd"
}

resource "azurerm_role_assignment" "cd_acr_push" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPush"
  principal_id         = data.azuread_service_principal.cd.object_id
}

resource "azurerm_role_assignment" "cd_container_apps_contributor" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Contributor"
  principal_id         = data.azuread_service_principal.cd.object_id
}

# ── Virtual Network ───────────────────────────────────────────────────────────
resource "azurerm_virtual_network" "main" {
  name                = "${local.name}-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_subnet" "services" {
  name                 = "services"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.1.0/24"]
  delegation {
    name = "container-apps"
    service_delegation {
      name = "Microsoft.App/environments"
    }
  }
}

resource "azurerm_subnet" "db" {
  name                 = "db"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.2.0/24"]
  service_endpoints    = ["Microsoft.Storage"]
  delegation {
    name = "pg-flexible"
    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# ── PostgreSQL Flexible Server ─────────────────────────────────────────────────
resource "azurerm_postgresql_flexible_server" "postgres" {
  name                   = "${local.name}-pg"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "15"
  delegated_subnet_id    = azurerm_subnet.db.id
  sku_name               = var.db_sku
  administrator_login    = "chitragupt"
  administrator_password = var.db_password
  storage_mb             = 32768
  zone                   = "1"

  high_availability {
    mode                      = var.environment == "production" ? "ZoneRedundant" : "Disabled"
    standby_availability_zone = var.environment == "production" ? "2" : null
  }

  backup_retention_days        = var.environment == "production" ? 30 : 7
  geo_redundant_backup_enabled = var.environment == "production"
  tags                         = local.tags
}

resource "azurerm_postgresql_flexible_server_database" "chitragupt" {
  name      = "chitragupt"
  server_id = azurerm_postgresql_flexible_server.postgres.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

resource "azurerm_postgresql_flexible_server_configuration" "pgvector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.postgres.id
  value     = "VECTOR"
}

# ── Azure Cache for Redis ──────────────────────────────────────────────────────
resource "azurerm_redis_cache" "main" {
  name                = "${local.name}-redis"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  capacity            = 1
  family              = "C"
  sku_name            = var.environment == "production" ? "Standard" : "Basic"
  enable_non_ssl_port = false
  minimum_tls_version = "1.2"
  tags                = local.tags
}

# ── Key Vault ─────────────────────────────────────────────────────────────────
data "azuread_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                        = substr(replace(local.name, "-", ""), 0, 24)
  resource_group_name         = azurerm_resource_group.main.name
  location                    = azurerm_resource_group.main.location
  tenant_id                   = data.azuread_client_config.current.tenant_id
  sku_name                    = "standard"
  purge_protection_enabled    = var.environment == "production"
  soft_delete_retention_days  = 7
  tags                        = local.tags
}

resource "azurerm_key_vault_access_policy" "runtime" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azuread_client_config.current.tenant_id
  object_id    = azurerm_user_assigned_identity.runtime.principal_id
  secret_permissions = ["Get", "List"]
}

resource "azurerm_key_vault_secret" "db_password" {
  name         = "db-password"
  value        = var.db_password
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_key_vault_access_policy.runtime]
}

resource "azurerm_key_vault_secret" "openrouter_key" {
  name         = "openrouter-api-key"
  value        = var.openrouter_api_key
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_key_vault_access_policy.runtime]
}

# ── Container Apps Environment ─────────────────────────────────────────────────
resource "azurerm_container_app_environment" "main" {
  name                       = "${local.name}-env"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  infrastructure_subnet_id   = azurerm_subnet.services.id
  tags                       = local.tags
}

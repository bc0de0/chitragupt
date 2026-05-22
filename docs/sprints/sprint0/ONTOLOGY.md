# Ontology: Entities and Relationships

**Phase:** Sprint 0 — Foundation
**Version:** 2.0 — Canonical
**Purpose:** Defines the complete structural grammar, data models, entity schemas, and relationships that Chitragupt will use to parse, understand, store, and manage business requirements. This document is the authoritative reference for the database schema, vector store metadata schema, and the API contract. The physical SQL implementation is in `DATABASE.md`.

---

## 1. Core Entities

The system must map unstructured text and structured inputs into a well-defined entity model. Every object in the system belongs to one of the entity families below.

---

### 1.1 Source Entities

These entities represent the raw inputs ingested into the system.

#### 1.1.1 `Document`

The root-level input artifact. Every ingested file, URL, chat session, or API payload is a Document.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `document_id` | UUID | ✅ | Unique identifier |
| `project_id` | UUID | ✅ | Parent project (FK) |
| `tenant_id` | UUID | ✅ | Owning organization (enforces isolation) |
| `name` | string | ✅ | Human-readable file or source name |
| `source_type` | enum | ✅ | `pdf`, `docx`, `txt`, `md`, `xlsx`, `confluence_url`, `jira_epic`, `linear_issue`, `notion_page`, `chat_session`, `web_url`, `audio`, `image`, `video` |
| `source_uri` | string | — | URL or file path of original source |
| `author` | string | — | Author or system that produced the document |
| `version_label` | string | — | Version string if document is versioned (e.g., "v2.1") |
| `file_hash` | string | — | SHA-256 of raw content for deduplication |
| `status` | enum | ✅ | `pending`, `processing`, `indexed`, `failed`, `tombstoned` |
| `ingested_at` | timestamp | ✅ | When the document was first ingested |
| `last_modified_at` | timestamp | — | Last known modification time of the source |
| `is_superseded` | boolean | ✅ | True if a newer version has replaced this document |
| `superseded_by` | UUID | — | FK to the Document that replaces this one |
| `trust_tier` | integer (1–5) | ✅ | Position in the epistemological hierarchy |
| `metadata` | jsonb | — | Arbitrary key-value metadata from the source system |

#### 1.1.2 `Chunk`

A semantically contiguous segment of a Document, stored in the vector database.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `chunk_id` | UUID | ✅ | Unique identifier |
| `document_id` | UUID | ✅ | Parent document (FK) |
| `tenant_id` | UUID | ✅ | Tenant isolation (denormalized for query performance) |
| `project_id` | UUID | ✅ | Parent project |
| `content` | text | ✅ | Raw text content of the chunk |
| `embedding` | vector(1536) | ✅ | Dense embedding vector |
| `sparse_vector` | jsonb | — | BM25 sparse vector for hybrid search |
| `chunk_index` | integer | ✅ | Ordinal position within the parent document |
| `token_count` | integer | ✅ | Number of tokens in this chunk |
| `start_char` | integer | — | Character offset in original document |
| `end_char` | integer | — | Character offset end in original document |
| `page_number` | integer | — | Page number (for paginated documents) |
| `section_title` | string | — | Nearest parent heading in the document structure |
| `valid_from` | timestamp | ✅ | When this chunk became active (ingestion time) |
| `valid_until` | timestamp | — | When this chunk was superseded (tombstone time) |
| `is_active` | boolean | ✅ | False for tombstoned chunks |
| `source_type` | enum | ✅ | Inherited from parent Document |
| `confidence_modifier` | float | — | Adjustment applied to retrieval scores for this chunk type (e.g., -0.15 for visual extractions) |

#### 1.1.3 `Stakeholder`

A person or system that produced or contributed to a source document.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `stakeholder_id` | UUID | ✅ | Unique identifier |
| `tenant_id` | UUID | ✅ | Owning organization |
| `name` | string | ✅ | Full name |
| `email` | string | — | Contact email |
| `role` | enum | ✅ | `client`, `product_manager`, `business_analyst`, `solutions_architect`, `engineer`, `delivery_lead`, `compliance_officer`, `external` |
| `authority_level` | enum | ✅ | `decision_maker`, `contributor`, `reviewer`, `observer` |
| `projects` | UUID[] | — | Projects this stakeholder is associated with |

---

### 1.2 Knowledge Entities

These entities represent the extracted and synthesized intelligence derived from source documents.

#### 1.2.1 `Requirement`

The primary unit of value. A documented need or condition extracted or synthesized from source chunks.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `requirement_id` | UUID | ✅ | Unique identifier |
| `project_id` | UUID | ✅ | Parent project |
| `tenant_id` | UUID | ✅ | Owning organization |
| `req_code` | string | ✅ | Human-readable ID (e.g., `FR-001`, `NFR-012`) |
| `type` | enum | ✅ | `functional`, `non_functional`, `business_rule`, `data_requirement`, `integration_requirement`, `compliance_requirement`, `ui_ux_requirement` |
| `category` | enum | — | `performance`, `security`, `usability`, `reliability`, `scalability`, `maintainability`, `portability` (for NFRs) |
| `description` | text | ✅ | The synthesized requirement statement |
| `priority` | enum | ✅ | `must_have`, `should_have`, `could_have`, `wont_have` (MoSCoW) |
| `source_chunks` | UUID[] | ✅ | Array of chunk IDs that support this requirement |
| `confidence_score` | float (0–1) | ✅ | Calibrated certainty score |
| `confidence_tier` | enum | ✅ | `explicit`, `synthesized`, `inferred`, `speculative` |
| `status` | enum | ✅ | `draft`, `synthesized`, `inferred`, `human_approved`, `human_rejected`, `under_review`, `conflicted`, `deprecated` |
| `acceptance_criteria` | jsonb | — | Array of AC objects (see sub-schema below) |
| `affected_actors` | UUID[] | — | Array of Actor entity IDs |
| `conflicts_with` | UUID[] | — | Array of conflicting Requirement IDs |
| `depends_on` | UUID[] | — | Requirements that must be resolved first |
| `version` | integer | ✅ | Monotonically increasing version number |
| `created_by_agent` | string | ✅ | Agent ID that generated this requirement |
| `last_modified_by` | string | ✅ | User ID or agent ID of last modifier |
| `created_at` | timestamp | ✅ | |
| `updated_at` | timestamp | ✅ | |
| `approved_at` | timestamp | — | Set when human approves; immutable thereafter |
| `approved_by` | UUID | — | User who approved |
| `human_override_text` | text | — | If human edited the description, the original AI text is preserved here |

**Acceptance Criteria sub-schema:**

```json
{
  "criteria_id": "AC-001",
  "type": "positive | negative | edge_case",
  "given": "...",
  "when": "...",
  "then": "...",
  "status": "draft | human_approved | human_rejected"
}
```

#### 1.2.2 `Constraint`

A limiting factor that restricts how a requirement can be fulfilled.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `constraint_id` | UUID | ✅ | |
| `project_id` | UUID | ✅ | |
| `constraint_code` | string | ✅ | e.g., `CON-001` |
| `type` | enum | ✅ | `technical`, `budget`, `timeline`, `regulatory`, `organizational`, `vendor` |
| `description` | text | ✅ | |
| `source_chunks` | UUID[] | ✅ | |
| `affects_requirements` | UUID[] | — | Requirements this constraint limits |
| `confidence_score` | float | ✅ | |
| `status` | enum | ✅ | `draft`, `human_approved`, `human_rejected` |

#### 1.2.3 `Assumption`

A condition assumed to be true by the system or a stakeholder that has not been verified.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assumption_id` | UUID | ✅ | |
| `assumption_code` | string | ✅ | e.g., `ASM-001` |
| `description` | text | ✅ | |
| `source_chunks` | UUID[] | — | Empty if pure inference |
| `assumed_by` | UUID | — | Stakeholder who stated it, if known |
| `risk_if_false` | enum | ✅ | `low`, `medium`, `high`, `critical` |
| `status` | enum | ✅ | `unverified`, `verified`, `disproven` |
| `verified_by` | UUID | — | Stakeholder who verified/disproved it |

#### 1.2.4 `Actor`

A person, persona, user role, or external system that interacts with the product.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `actor_id` | UUID | ✅ | |
| `project_id` | UUID | ✅ | |
| `name` | string | ✅ | e.g., "Admin", "Payment Gateway", "End User" |
| `actor_type` | enum | ✅ | `human_user`, `system`, `external_service`, `organization` |
| `description` | text | — | |
| `permissions` | string[] | — | Inferred permissions or capabilities |
| `source_chunks` | UUID[] | — | Where this actor was first mentioned |

---

### 1.3 State & Workflow Entities

These entities represent the dynamic state of the specification process.

#### 1.3.1 `Conflict`

A logical contradiction between two or more Chunks, Requirements, or Constraints.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `conflict_id` | UUID | ✅ | |
| `project_id` | UUID | ✅ | |
| `conflict_type` | enum | ✅ | `direct_contradiction`, `scope_overlap`, `version_conflict`, `implicit_contradiction` |
| `description` | text | ✅ | Narrative description of the conflict |
| `source_a_chunk_id` | UUID | ✅ | First conflicting source chunk |
| `source_b_chunk_id` | UUID | ✅ | Second conflicting source chunk |
| `affected_requirements` | UUID[] | — | Requirements blocked by this conflict |
| `status` | enum | ✅ | `open`, `resolved_a`, `resolved_b`, `resolved_manual`, `escalated` |
| `resolution` | text | — | Human-provided resolution rationale |
| `resolved_by` | UUID | — | Stakeholder who resolved it |
| `resolved_at` | timestamp | — | |
| `severity` | enum | ✅ | `low`, `medium`, `high`, `blocking` |

#### 1.3.2 `Gap` (Open Question)

A missing piece of knowledge required to complete the Specification.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `gap_id` | UUID | ✅ | |
| `project_id` | UUID | ✅ | |
| `gap_code` | string | ✅ | e.g., `OQ-001` |
| `type` | enum | ✅ | `missing_requirement`, `missing_nfr`, `missing_actor`, `missing_constraint`, `missing_acceptance_criteria`, `ambiguous_requirement`, `compliance_gap` |
| `description` | text | ✅ | What information is missing and why it matters |
| `blocking_requirements` | UUID[] | — | Requirements that cannot be finalized until this gap is closed |
| `assigned_to` | UUID | — | Stakeholder responsible for answering |
| `status` | enum | ✅ | `open`, `answered`, `deferred`, `wont_answer` |
| `answer` | text | — | Stakeholder-provided response |
| `answered_at` | timestamp | — | |
| `priority` | enum | ✅ | `must_resolve`, `should_resolve`, `nice_to_know` |

#### 1.3.3 `Specification`

The final output artifact — an aggregated, versioned collection of approved Requirements, Constraints, and Assumptions.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `spec_id` | UUID | ✅ | |
| `project_id` | UUID | ✅ | |
| `tenant_id` | UUID | ✅ | |
| `version` | integer | ✅ | Monotonically increasing |
| `version_label` | string | — | e.g., "v1.0 — Draft", "v2.0 — Client Approved" |
| `status` | enum | ✅ | `draft`, `in_review`, `approved`, `locked`, `deprecated` |
| `requirements` | UUID[] | ✅ | Ordered list of Requirement IDs |
| `constraints` | UUID[] | — | Constraint IDs |
| `assumptions` | UUID[] | — | Assumption IDs |
| `open_questions` | UUID[] | — | Unresolved Gap IDs |
| `conflicts` | UUID[] | — | Unresolved Conflict IDs |
| `template_id` | UUID | — | Domain template applied |
| `created_at` | timestamp | ✅ | |
| `locked_at` | timestamp | — | Set when status becomes `locked`; immutable thereafter |
| `locked_by` | UUID | — | |
| `export_formats` | string[] | — | Formats this spec has been exported to: `markdown`, `docx`, `pdf`, `brd_docx`, `brd_pdf`, `hld_mermaid`, `hld_png`, `hld_svg` |
| `client_sign_off_id` | UUID | — | FK to ClientSignOff; set when the client formally approves this version; triggers `status → locked` |
| `completeness_score` | float (0–1) | — | System-calculated completeness against domain checklist |

---

### 1.4 Project & Workspace Entities

#### 1.4.1 `Project`

The top-level container for a requirements analysis engagement.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `project_id` | UUID | ✅ | |
| `tenant_id` | UUID | ✅ | |
| `name` | string | ✅ | |
| `description` | text | — | |
| `domain` | enum | ✅ | `fintech`, `healthcare`, `ecommerce`, `logistics`, `saas_b2b`, `government`, `general` |
| `status` | enum | ✅ | `discovery`, `ingestion`, `analysis`, `review`, `approved`, `archived` |
| `template_id` | UUID | — | Domain template applied at creation |
| `owner_id` | UUID | ✅ | User who created/owns this project |
| `collaborators` | UUID[] | — | User IDs with access |
| `stakeholders` | UUID[] | — | External stakeholder IDs |
| `budget_cap_usd` | decimal | — | Maximum allowed LLM cost for this project |
| `cost_incurred_usd` | decimal | ✅ | Running total of LLM API cost |
| `created_at` | timestamp | ✅ | |
| `target_spec_date` | date | — | Target date for spec completion |

#### 1.4.2 `Workspace` (Organization)

The tenant-level container. All data in the system is scoped to a Workspace.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `workspace_id` | UUID | ✅ | = `tenant_id` throughout the system |
| `name` | string | ✅ | Organization name |
| `plan` | enum | ✅ | `starter`, `professional`, `business`, `enterprise` |
| `vector_namespace` | string | ✅ | Dedicated namespace in the vector store |
| `llm_api_keys` | jsonb | — | Encrypted; org-level API key overrides |
| `model_preferences` | jsonb | — | Default model tier assignments |
| `data_residency` | enum | — | `us`, `eu`, `apac`, `on_premise` |
| `compliance_flags` | string[] | — | e.g., `["GDPR", "HIPAA", "SOC2"]` |
| `retention_days` | integer | ✅ | Default document retention policy (default: 90) |
| `sso_config` | jsonb | — | SAML/OIDC configuration |
| `created_at` | timestamp | ✅ | |
| `monthly_budget_cap_usd` | decimal | — | Org-level monthly LLM spend cap |

#### 1.4.3 `DomainTemplate`

A reusable completeness checklist and output structure for a specific industry vertical.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `template_id` | UUID | ✅ | |
| `name` | string | ✅ | e.g., "Fintech Payments Template" |
| `domain` | enum | ✅ | |
| `completeness_checklist` | jsonb | ✅ | Array of required requirement categories with descriptions |
| `output_sections` | jsonb | ✅ | Ordered list of spec sections with descriptions |
| `domain_glossary` | jsonb | — | Key terms and their domain-specific definitions |
| `compliance_requirements` | string[] | — | Regulatory standards relevant to this domain |
| `brd_sections` | jsonb | — | Ordered BRD section definitions mapping requirement types to BRD chapter layout |
| `hld_component_hints` | jsonb | — | System component categories to extract when generating the HLD |
| `is_system_template` | boolean | ✅ | True = Chitragupt-provided; False = org-customized |
| `owner_workspace_id` | UUID | — | Null for system templates; set for org-customized |

---

### 1.5 User & Session Entities

#### 1.5.1 `User`

A human user of the BRA system (internal — BA, PM, architect, lead).

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `user_id` | UUID | ✅ | |
| `workspace_id` | UUID | ✅ | |
| `email` | string | ✅ | |
| `name` | string | ✅ | |
| `role` | enum | ✅ | `admin`, `business_analyst`, `product_manager`, `solutions_architect`, `delivery_lead`, `viewer` |
| `permissions` | string[] | ✅ | Fine-grained permission set |
| `ui_mode_preference` | enum | — | `guided`, `express`, `expert` |
| `model_tier_preference` | enum | — | `auto`, `fast`, `quality`, `premium` |
| `notification_preferences` | jsonb | — | Email/webhook notification settings |
| `created_at` | timestamp | ✅ | |
| `last_active_at` | timestamp | — | |

#### 1.5.2 `Session`

A bounded interaction context — typically one project elicitation session.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `session_id` | UUID | ✅ | |
| `project_id` | UUID | ✅ | |
| `user_id` | UUID | ✅ | |
| `session_type` | enum | ✅ | `elicitation`, `review`, `export`, `re_generation` |
| `messages` | jsonb | ✅ | Ordered array of chat messages |
| `active_agents` | string[] | — | Agent IDs currently running in this session |
| `state` | jsonb | ✅ | LangGraph state machine serialized state |
| `started_at` | timestamp | ✅ | |
| `ended_at` | timestamp | — | |
| `pii_scrubbed` | boolean | ✅ | True if PII was detected and redacted before embedding |

---

### 1.6 Version & Audit Entities

#### 1.6.1 `RequirementVersion`

Immutable snapshot of a Requirement at each point it changes.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `version_id` | UUID | ✅ | |
| `requirement_id` | UUID | ✅ | |
| `version` | integer | ✅ | Sequential version number |
| `description` | text | ✅ | Description at this version |
| `status` | enum | ✅ | Status at this version |
| `confidence_score` | float | ✅ | |
| `modified_by` | string | ✅ | User ID or agent ID |
| `modification_reason` | enum | — | `ai_synthesis`, `human_edit`, `human_approval`, `ai_regeneration`, `conflict_resolution` |
| `diff_from_previous` | text | — | Textual diff from prior version |
| `created_at` | timestamp | ✅ | When this version was created |

#### 1.6.2 `AuditLog`

Append-only record of every meaningful action in the system.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `log_id` | UUID | ✅ | |
| `tenant_id` | UUID | ✅ | |
| `project_id` | UUID | — | |
| `actor_type` | enum | ✅ | `human`, `agent`, `system` |
| `actor_id` | string | ✅ | User ID, agent name, or "system" |
| `action` | string | ✅ | e.g., `requirement.approved`, `document.ingested`, `conflict.raised` |
| `entity_type` | string | ✅ | e.g., `Requirement`, `Document`, `Conflict` |
| `entity_id` | UUID | ✅ | |
| `before_state` | jsonb | — | Entity state before action (for diffs) |
| `after_state` | jsonb | — | Entity state after action |
| `metadata` | jsonb | — | Additional context (IP, model ID, token count) |
| `timestamp` | timestamp | ✅ | Immutable; server-set |

---

### 1.7 Cost & Usage Tracking Entities

#### 1.7.1 `LLMCallLog`

Record of every LLM API call made by any agent.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `call_id` | UUID | ✅ | |
| `project_id` | UUID | ✅ | |
| `tenant_id` | UUID | ✅ | |
| `agent_name` | string | ✅ | Which agent made the call |
| `model_id` | string | ✅ | e.g., `claude-sonnet-4-6`, `gemini-2.0-flash` |
| `model_tier` | enum | ✅ | `fast`, `quality`, `premium` |
| `prompt_tokens` | integer | ✅ | Input token count |
| `completion_tokens` | integer | ✅ | Output token count |
| `cached_tokens` | integer | — | Tokens served from prompt cache (cost = 0) |
| `cost_usd` | decimal | ✅ | Calculated cost for this call |
| `latency_ms` | integer | ✅ | End-to-end latency |
| `success` | boolean | ✅ | |
| `error_code` | string | — | Provider error code if failed |
| `fallback_used` | boolean | — | True if primary provider failed and fallback was used |
| `timestamp` | timestamp | ✅ | |

#### 1.7.2 `ProjectCostSummary`

Rolling cost aggregation per project — materialized view or computed on query.

| Field | Type | Description |
| :--- | :--- | :--- |
| `project_id` | UUID | |
| `total_cost_usd` | decimal | Sum of all LLMCallLog costs for this project |
| `cost_by_agent` | jsonb | Breakdown per agent name |
| `cost_by_model` | jsonb | Breakdown per model |
| `prompt_cache_savings_usd` | decimal | Estimated savings from cached tokens |
| `total_calls` | integer | |
| `total_tokens` | integer | |
| `last_calculated_at` | timestamp | |

---

### 1.8 Output & Sign-Off Entities

#### 1.8.1 `ExportArtifact`

A versioned output file generated from an approved or locked Specification.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `artifact_id` | UUID | ✅ | |
| `spec_id` | UUID | ✅ | Parent Specification |
| `project_id` | UUID | ✅ | |
| `tenant_id` | UUID | ✅ | |
| `artifact_type` | enum | ✅ | `brd_docx`, `brd_pdf`, `hld_mermaid`, `hld_png`, `hld_svg`, `spec_markdown`, `spec_docx`, `spec_pdf` |
| `storage_uri` | string | ✅ | S3 path: `s3://.../{{tenant_id}}/{{project_id}}/exports/{{artifact_id}}.{{ext}}` |
| `file_hash` | string | ✅ | SHA-256 of file contents for integrity verification |
| `generated_at` | timestamp | ✅ | |
| `generated_by` | string | ✅ | Agent ID or user ID that triggered generation |
| `brd_template_id` | UUID | — | BRD template applied (for `brd_*` artifact types) |
| `spec_version` | integer | ✅ | Version of the parent Specification at export time |
| `is_sign_off_copy` | boolean | ✅ | True if this artifact was the one sent for client sign-off |
| `sign_off_id` | UUID | — | FK to ClientSignOff; set once the client approves this artifact |

#### 1.8.2 `BRDTemplate`

A structured template that maps Specification contents into a formal Business Requirements Document layout.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `brd_template_id` | UUID | ✅ | |
| `name` | string | ✅ | e.g., "Standard BRD v1", "Fintech Payments BRD" |
| `domain` | enum | — | If domain-specific; null for general-purpose templates |
| `sections` | jsonb | ✅ | Ordered section definitions (see sub-schema below) |
| `cover_page_fields` | jsonb | — | Fields rendered on the cover page: project name, client, date, version, signatories |
| `include_traceability_matrix` | boolean | ✅ | Whether to append a source-to-requirement traceability table |
| `include_glossary` | boolean | ✅ | Whether to append the domain glossary |
| `is_system_template` | boolean | ✅ | True = Chitragupt-provided; False = org-customized |
| `owner_workspace_id` | UUID | — | Null for system templates; set for org-customized copies |

**BRD Section sub-schema:**

```json
{
  "section_id": "BRD-S-01",
  "title": "Executive Summary",
  "description": "High-level business context and project objective",
  "source": "synthesized",
  "requirement_types": [],
  "is_required": true,
  "order": 1
}
```

Valid `source` values: `synthesized`, `functional_requirements`, `non_functional_requirements`, `business_rules`, `data_requirements`, `integration_requirements`, `compliance_requirements`, `constraints`, `assumptions`, `open_questions`, `actors`.

#### 1.8.3 `ClientSignOff`

A tamper-evident record of formal client approval of a specific ExportArtifact. Creating this record and setting `status = signed` is the only mechanism that transitions a Specification to `locked`.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `sign_off_id` | UUID | ✅ | |
| `spec_id` | UUID | ✅ | The Specification version being approved |
| `artifact_id` | UUID | ✅ | The specific ExportArtifact the client reviewed |
| `project_id` | UUID | ✅ | |
| `tenant_id` | UUID | ✅ | |
| `signed_by_stakeholder_id` | UUID | ✅ | FK to Stakeholder (the client signatory) |
| `signed_by_email` | string | ✅ | Email confirmed at time of signing; immutable |
| `signed_at` | timestamp | — | Server-set; immutable; null until status = `signed` |
| `signature_token` | string | ✅ | Single-use HMAC token from the sign-off invite link; burned on first use |
| `token_expires_at` | timestamp | ✅ | 7 days after invite creation |
| `sign_off_method` | enum | ✅ | `email_link`, `in_app`, `wet_signature_upload` |
| `status` | enum | ✅ | `pending`, `signed`, `declined`, `expired` |
| `declined_reason` | text | — | Stakeholder-provided reason when status = `declined` |
| `ip_address` | string | — | IP address at time of signing (audit record) |

**Effect of `status = signed`:** `Specification.status → locked`, `Specification.client_sign_off_id` set, `Specification.locked_at` set. No UPDATE operations are permitted on the Specification or its Requirements thereafter. Outbound webhooks and Jira pushes are unblocked (INV-HITL-02).

---

## 2. Relationships (The Knowledge Graph)

### 2.1 Core Entity Relationships

```
Workspace
  └── HAS_MANY Projects
  └── HAS_MANY Users
  └── HAS_MANY DomainTemplates (custom)

Project
  └── HAS_MANY Documents
  └── HAS_MANY Requirements
  └── HAS_MANY Constraints
  └── HAS_MANY Assumptions
  └── HAS_MANY Actors
  └── HAS_MANY Conflicts
  └── HAS_MANY Gaps
  └── HAS_MANY Sessions
  └── HAS_MANY Specifications (versioned)
  └── BELONGS_TO DomainTemplate

Document
  └── HAS_MANY Chunks
  └── BELONGS_TO Stakeholder (author)
  └── MAY_SUPERSEDE another Document

Chunk
  └── BELONGS_TO Document
  └── SUPPORTS many Requirements (M2M via source_chunks)
  └── INVOLVED_IN many Conflicts

Requirement
  └── SUPPORTED_BY many Chunks
  └── AFFECTS many Actors
  └── CONFLICTS_WITH many Requirements
  └── DEPENDS_ON many Requirements
  └── HAS_MANY AcceptanceCriteria
  └── HAS_MANY RequirementVersions (audit trail)

Conflict
  └── REFERENCES two or more Chunks
  └── BLOCKS many Requirements
  └── RESOLVED_BY Stakeholder

Gap
  └── BLOCKS many Requirements
  └── ASSIGNED_TO Stakeholder

Specification
  └── AGGREGATES many Requirements
  └── AGGREGATES many Constraints
  └── AGGREGATES many Assumptions
  └── REFERENCES many Gaps (unresolved)
  └── REFERENCES many Conflicts (unresolved)
  └── BUILT_FROM DomainTemplate
  └── HAS_MANY ExportArtifacts
  └── HAS_ONE ClientSignOff (only when locked)

ExportArtifact
  └── BELONGS_TO Specification
  └── RENDERED_FROM BRDTemplate (for brd_* artifact types)
  └── MAY_HAVE one ClientSignOff

ClientSignOff
  └── REFERENCES Specification (the version approved)
  └── REFERENCES ExportArtifact (the document reviewed)
  └── SIGNED_BY Stakeholder
```

### 2.2 Relationship Detail Table

| Relationship | Cardinality | Notes |
| :--- | :--- | :--- |
| `Document HAS_MANY Chunk` | 1:N | A document decomposes into many chunks |
| `Chunk SUPPORTS Requirement` | M:N | One chunk may support many requirements; one requirement may draw from many chunks |
| `Requirement CONFLICTS_WITH Requirement` | M:N | Self-referential; conflict is symmetric |
| `Requirement DEPENDS_ON Requirement` | M:N | Dependency graph; must be a DAG (no circular dependencies) |
| `Gap BLOCKS Requirement` | M:N | Unresolved gap prevents requirement finalization |
| `Stakeholder RESOLVES Conflict` | 1:N | One stakeholder resolves; many conflicts may be resolved |
| `Specification AGGREGATES Requirement` | M:N | A spec version includes specific requirements |
| `User APPROVES Requirement` | 1:N | One user approves; approval is permanent |
| `Project BELONGS_TO Workspace` | N:1 | Many projects per organization |
| `LLMCallLog BELONGS_TO Project` | N:1 | Full cost trail per project |
| `Specification HAS_MANY ExportArtifact` | 1:N | One spec version may produce multiple export formats |
| `ExportArtifact RENDERED_FROM BRDTemplate` | N:1 | Many exports may share a template; only applies to `brd_*` types |
| `ExportArtifact HAS_ONE ClientSignOff` | 1:0..1 | Only the artifact sent for sign-off carries a ClientSignOff record |
| `ClientSignOff SIGNED_BY Stakeholder` | N:1 | The external client who formally approved the document |

---

## 3. The "Requirement" Schema (Complete)

A synthesized Requirement object must conform to this standard before it can enter the final specification:

```json
{
  "requirement_id": "uuid",
  "project_id": "uuid",
  "tenant_id": "uuid",
  "req_code": "FR-001",
  "type": "functional",
  "category": null,
  "description": "The system shall allow administrators to export payment reconciliation reports in CSV format.",
  "priority": "must_have",
  "source_chunks": ["chunk-uuid-1", "chunk-uuid-2"],
  "confidence_score": 0.92,
  "confidence_tier": "explicit",
  "status": "draft",
  "acceptance_criteria": [
    {
      "criteria_id": "AC-001",
      "type": "positive",
      "given": "An administrator is logged in",
      "when": "They click 'Export Report' and select CSV format",
      "then": "A CSV file is downloaded containing all reconciliation records for the selected date range"
    },
    {
      "criteria_id": "AC-002",
      "type": "negative",
      "given": "An administrator is logged in",
      "when": "They attempt to export a report with an invalid date range (start > end)",
      "then": "The system displays an error: 'Start date must be before end date' and no file is downloaded"
    }
  ],
  "affected_actors": ["actor-uuid-admin"],
  "conflicts_with": [],
  "depends_on": [],
  "version": 1,
  "created_by_agent": "synthesis_agent",
  "last_modified_by": "synthesis_agent",
  "created_at": "2026-05-19T10:30:00Z",
  "updated_at": "2026-05-19T10:30:00Z",
  "approved_at": null,
  "approved_by": null,
  "human_override_text": null
}
```

---

## 4. Vector Store Metadata Schema

Every vector stored in the vector database must carry structured metadata to enable filtered retrieval. This is the queryable metadata envelope for each chunk embedding.

```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "project_id": "uuid",
  "tenant_id": "uuid",
  "source_type": "pdf",
  "trust_tier": 3,
  "page_number": 4,
  "section_title": "Payment Processing Requirements",
  "valid_from": "2026-05-19T10:00:00Z",
  "valid_until": null,
  "is_active": true,
  "confidence_modifier": 0.0,
  "language": "en",
  "token_count": 412
}
```

**Mandatory filters applied at every retrieval query:**
- `tenant_id == {current_tenant_id}` — Tenant isolation (never relaxed)
- `project_id == {current_project_id}` — Project scope
- `is_active == true` — Exclude tombstoned chunks
- `valid_until IS NULL OR valid_until > NOW()` — Exclude expired knowledge

---

## 5. Agent State Machine Schema

The LangGraph state machine must serialize its state after each step. The canonical state object is:

```json
{
  "project_id": "uuid",
  "session_id": "uuid",
  "current_agent": "synthesis_agent",
  "phase": "synthesis",
  "ingested_documents": ["doc-uuid-1", "doc-uuid-2"],
  "active_queries": ["payment reconciliation behaviors"],
  "retrieved_chunks": [{"chunk_id": "...", "score": 0.89}],
  "draft_requirements": ["req-uuid-1"],
  "open_conflicts": ["conflict-uuid-1"],
  "open_gaps": ["gap-uuid-1"],
  "human_pending_actions": [],
  "completed_sections": ["functional_requirements"],
  "remaining_sections": ["non_functional_requirements", "constraints"],
  "total_cost_so_far_usd": 0.34,
  "iteration_count": 2,
  "last_updated": "2026-05-19T10:35:00Z"
}
```

---

> Chitragupt Ontology · v2.0 · Sprint 0 Canonical · May 2026

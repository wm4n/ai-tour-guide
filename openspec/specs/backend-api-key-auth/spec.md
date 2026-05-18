# Capability: Backend API Key Authentication

## Purpose

Secures backend API endpoints with API key authentication, supporting both production (API key required) and development (API key optional) modes.

---

## Requirements

### Requirement: API_KEY config field in backend settings
The `AppConfig` class SHALL include `api_key: str = Field("", alias="API_KEY")`. When `API_KEY` is not set in the environment, `api_key` defaults to empty string.

#### Scenario: API_KEY absent defaults to empty string
- **WHEN** `AppConfig()` is constructed without `API_KEY` in the environment
- **THEN** `config.api_key == ""`

#### Scenario: API_KEY set from environment
- **WHEN** `API_KEY=secret123` is in the environment
- **THEN** `config.api_key == "secret123"`

---

### Requirement: X-Api-Key middleware enforces authentication
The backend SHALL register an HTTP middleware that checks the `X-Api-Key` request header. If `api_key` is empty (dev mode), ALL requests are allowed. If `api_key` is non-empty, requests without a matching `X-Api-Key` header SHALL receive HTTP 401.

#### Scenario: Empty api_key allows all requests (dev mode)
- **WHEN** `api_key == ""` and a request arrives without `X-Api-Key` header
- **THEN** the request is passed through and returns a 2xx response

#### Scenario: Valid X-Api-Key header allowed
- **WHEN** `api_key == "secret"` and request has `X-Api-Key: secret`
- **THEN** the request proceeds and returns a 2xx response

#### Scenario: Invalid X-Api-Key header rejected
- **WHEN** `api_key == "secret"` and request has `X-Api-Key: wrong`
- **THEN** middleware returns HTTP 401

#### Scenario: Missing X-Api-Key header rejected when key configured
- **WHEN** `api_key == "secret"` and request has no `X-Api-Key` header
- **THEN** middleware returns HTTP 401

---

### Requirement: BackendClient attaches X-Api-Key header
The Flutter `BackendClient` constructor SHALL accept an `apiKey` parameter. All outgoing HTTP requests SHALL include the `X-Api-Key: <apiKey>` header. When `apiKey` is empty string, the header is still sent (backend dev mode accepts it).

#### Scenario: BackendClient sends X-Api-Key on every request
- **WHEN** `BackendClient(apiKey: "secret").get("/poi/nearby", ...)`
- **THEN** the HTTP request includes `X-Api-Key: secret` header

#### Scenario: BackendClient with empty apiKey still sends header
- **WHEN** `BackendClient(apiKey: "").get("/healthz")`
- **THEN** the HTTP request includes `X-Api-Key: ` header (empty value)

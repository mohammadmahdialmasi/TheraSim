# Authentication and Credential Security Audit

**Audit date:** 2026-11-20
**Scope:** Source-inspected authentication and provider-credential design
**Status:** Inspected design only; independent security review blocked/unverified

This document records behavior visible in the current source and tests. It does
not claim a clean security audit, clinical safety, penetration-test coverage,
or absence of vulnerabilities.

## Independent review status

The requested independent security/authentication review could not complete
because no model endpoint was available to the reviewer. It therefore remains
**BLOCKED/UNVERIFIED**. The implementation checks below do not substitute for
that independent review, and this repository must not describe the release as
security-reviewed or clean until one is completed.

## Local authentication

TheraSim implements one fixed local reviewer account in the operational SQLite
database:

- account initialization is restricted to loopback clients;
- initialization rejects a pre-existing account and requires a reviewer name
  plus a password of 12–1024 characters;
- passwords are hashed with Python `hashlib.scrypt` using a random 16-byte
  salt and a derived-key format stored in SQLite;
- login attempts are hashed by client IP/key and throttled at five attempts
  per 15-minute window;
- successful login creates a cryptographically random bearer token with an
  eight-hour lifetime;
- only a SHA-256 digest of each bearer token is stored in the session table;
- logout revokes the token, and expired or revoked sessions are deleted during
  normal authentication maintenance.

This is local-account authentication, not multi-user authorization. Password
recovery and account recovery are not implemented. The bearer token is returned
to the browser and is not a separate hardware-backed credential.

## Authentication storage limitations

The live operational SQLite database stores the scrypt password hash and
bearer-session hashes, while live database encryption at rest is not
implemented. Database and log access is therefore protected primarily by host
filesystem permissions and account separation. This design should not be
presented as protection against a process running as the same Windows user or
an attacker who obtains local account access.

Initialization requires loopback access to the HTTP server. Login itself is
applicable to requests reaching that server, and the service binds locally
rather than providing remote access by default. A loopback-only bind is a
network boundary, not a complete authentication or host-security boundary.

## Provider credential storage

Provider configuration is stored separately from the operational SQLite
database in `provider-settings.json`.

### Windows behavior

- saved API keys are protected with `CryptProtectData` through Windows DPAPI;
- protection uses the current Windows user context and no
  `CRYPTPROTECT_LOCAL_MACHINE` mode;
- the base64-encoded DPAPI blob is stored in
  `api_key_protected`; the plaintext key is not written by normal saves;
- the settings API reports only whether a key is configured and never returns
  the key;
- startup reads the protected value through `CryptUnprotectData`;
- provider-specific environment API keys override saved values at runtime;
- startup migrates a legacy `api_key` plaintext field by protecting it,
  replacing it with `api_key_protected`, removing the plaintext field, and
  writing the settings file.

This behavior is user-scoped at the Windows account level and may also depend
on the current machine/profile context. DPAPI is not an application master
secret: a process running with sufficient access to the current Windows account
or a compromised host may be able to unprotect or observe credentials.
The protected value is not guaranteed to remain usable after account, profile,
machine, or recovery changes. Public copies of provider settings should still
be treated as sensitive because other provider fields and host configuration
may disclose operational details.

### Non-Windows behavior

Persistent provider-key storage is not implemented on non-Windows platforms.
Saving or loading a provider credential is rejected by the credential-store
implementation when it detects a non-Windows host. Provider credentials must
be supplied through provider-specific environment variables. Explicit
environment values take precedence over saved UI settings at startup and are
not persisted by TheraSim. A legacy plaintext key may not be migrated on a
non-Windows host.

## Provider endpoint and diagnostic boundaries

Provider URLs accept HTTP(S) only, reject embedded credentials and URL queries
or fragments, and reject non-loopback HTTP endpoints. Loopback HTTP and remote
HTTPS endpoints are supported when explicitly configured. Connection tests and
model requests are sent to the selected endpoint, which may be remote. Provider
URLs and key values are not returned by provider settings responses, and support
export allowlists omit provider URLs and model identifier values.

These boundaries reduce accidental disclosure and unsafe remote configuration;
they do not prove endpoint ownership, server authentication, TLS configuration,
or the confidentiality of data sent to a remote provider.

## Source-visible verification

Focused tests cover account initialization, login/rate limiting, bearer-session
authentication, provider environment precedence, URL validation, and provider
settings redaction. The independent security review remains unverified because
it did not execute. Passing unit tests and dependency scans are not an
independent security assessment.

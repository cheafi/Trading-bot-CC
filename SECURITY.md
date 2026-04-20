# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 6.x     | ✅ Current release |
| < 6.0   | ❌ No support      |

## Reporting a Vulnerability

If you discover a security vulnerability, **do not open a public issue**.

Instead, please email the maintainers privately or use GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature on this repository.

We will acknowledge receipt within 48 hours and aim to provide a fix or
mitigation plan within 7 days for critical issues.

---

## Secrets and Credentials

### Never Commit Secrets

This project requires API keys and tokens for brokers, Discord, LLM providers,
and market data services. **None of these should ever appear in source control.**

- Copy `.env.example` → `.env` and fill in your values.
- `.env` is already in `.gitignore`.
- Never hardcode tokens, passwords, or API keys in source files.
- Use `openssl rand -hex 32` to generate secure secrets.

### Least-Privilege Guidance

| Credential | Minimum Scope Needed |
|---|---|
| **Discord Bot Token** | `bot` scope, `Send Messages`, `Embed Links`, `Read Message History` in designated channels only. Do **not** grant `Administrator`. |
| **Broker API Keys** | Paper/sandbox mode first. Read-only where possible. Never grant withdrawal permissions. |
| **OpenAI / Azure OpenAI** | Standard API access. No fine-tuning or admin access needed. |
| **Database** | Application-level user, not superuser. Restrict to the `tradingai` database only. |
| **Market Data APIs** | Free-tier or read-only keys are sufficient for most features. |

### Environment Variable Hygiene

- Rotate secrets periodically.
- Use different credentials for development vs. production.
- If you suspect a key has leaked, revoke and regenerate immediately.
- Never paste tokens into Discord channels, GitHub issues, or logs.

### GitHub Actions

- All secrets used in CI/CD are stored as GitHub Actions Secrets (encrypted).
- Workflows never print secrets to logs.
- Review workflow files before granting `write` permissions.

### Docker Deployments

- Change all default passwords in `.env` before deploying.
- Do not expose Postgres, Redis, Grafana, or pgAdmin ports to the public internet
  unless behind authentication and a firewall.
- Use Docker secrets or a vault for production deployments.

---

## What Is NOT Production-Ready

Be honest about current maturity:

| Component | Status |
|---|---|
| Paper trading engine | ✅ Functional for simulation |
| Live broker execution | ⚠️ Experimental — use at your own risk |
| Signal scoring | ⚠️ Research-quality — not validated at scale |
| Options research | ⚠️ Synthetic data only — no live chains |
| Data accuracy | ⚠️ Depends on upstream sources (yfinance, etc.) |
| AI/LLM outputs | ⚠️ May hallucinate — always verify |

---

## Dependency Security

- Pin all dependencies in `pyproject.toml`.
- Run `pip audit` or `safety check` periodically.
- Review Dependabot / Renovate alerts if enabled.
- Avoid installing packages from untrusted sources.

---

## Responsible Disclosure

We appreciate security researchers who help keep this project safe.
If your report leads to a fix, we will credit you in the changelog
(unless you prefer to remain anonymous).

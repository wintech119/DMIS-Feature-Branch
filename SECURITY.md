# DMIS Security Guide

This document describes how to run security scans on the DMIS (Disaster Management Information System) codebase and outlines the security controls implemented in the application.

## Table of Contents

- [Security Scanning Tools](#security-scanning-tools)
- [How to Run Security Scans Locally](#how-to-run-security-scans-locally)
- [CI/CD Integration](#cicd-integration)
- [Security Controls](#security-controls)
- [Reporting Security Issues](#reporting-security-issues)

---

## Security Scanning Tools

DMIS uses the following static application security testing (SAST) tools:

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **Bandit** | Python security linter | `bandit.yml` |
| **Semgrep** | Multi-language SAST scanner | `semgrep.yml` |

### What They Detect

- **SQL Injection** - String formatting in SQL queries
- **Command Injection** - Unsafe subprocess/os.system calls
- **Cross-Site Scripting (XSS)** - Unescaped user input in templates
- **Code Injection** - Dangerous eval/exec usage
- **Weak Cryptography** - MD5/SHA1 for security purposes
- **Hardcoded Secrets** - Passwords and API keys in code
- **Path Traversal** - Unvalidated file paths
- **Open Redirect** - Unvalidated redirect URLs
- **SSRF** - Unvalidated outbound requests

---

## How to Run Security Scans Locally

### Prerequisites

Install the scanning tools:

```bash
pip install bandit semgrep
```

### Quick Scan (Recommended)

Run the automated SAST script:

```bash
# Make the script executable (first time only)
chmod +x scripts/run_sast.sh

# Run full security scan
./scripts/run_sast.sh

# Quick scan (high severity only)
./scripts/run_sast.sh --quick

# Generate HTML/JSON reports
./scripts/run_sast.sh --report
```

### Manual Bandit Scan

```bash
# Full scan with configuration
bandit -r app/ drims_app.py -c bandit.yml

# High severity only
bandit -r app/ drims_app.py -c bandit.yml -ll

# Generate JSON report
bandit -r app/ drims_app.py -c bandit.yml -f json -o bandit-report.json

# Generate HTML report
bandit -r app/ drims_app.py -c bandit.yml -f html -o bandit-report.html
```

### Manual Semgrep Scan

```bash
# Scan with custom rules
semgrep --config semgrep.yml app/ drims_app.py

# Include community rules
semgrep --config semgrep.yml --config p/python --config p/flask app/ drims_app.py

# OWASP Top 10 rules
semgrep --config p/owasp-top-ten app/ drims_app.py

# Generate JSON report
semgrep --config semgrep.yml --json -o semgrep-report.json app/ drims_app.py

# Errors only
semgrep --config semgrep.yml --severity ERROR app/ drims_app.py
```

### Understanding Results

| Severity | Action Required |
|----------|-----------------|
| **HIGH/ERROR** | Must fix before deployment |
| **MEDIUM/WARNING** | Should fix, review for false positives |
| **LOW/INFO** | Review and fix if applicable |

---

## CI/CD Integration

### GitHub Actions

The `.github/workflows/security-sast.yml` workflow automatically runs on:

- Push to `main`, `master`, or `develop` branches
- Pull requests to protected branches
- Manual workflow dispatch

**Workflow Behavior:**
- **FAIL** if Critical/High severity issues are detected
- **PASS** with warnings for Medium/Low issues
- Results are uploaded to GitHub Security tab (SARIF format)
- Artifacts available for download

### Running Locally Before Push

Always run scans before pushing:

```bash
./scripts/run_sast.sh
```

If the scan fails (exit code 1), fix the issues before pushing.

---

## Security Controls

DMIS implements the following security controls:

### Application Security

| Control | Implementation |
|---------|----------------|
| CSRF Protection | Flask-WTF with token validation |
| XSS Prevention | Jinja2 auto-escaping, CSP headers |
| SQL Injection | SQLAlchemy ORM, parameterized queries |
| Authentication | Flask-Login with password hashing |
| Authorization | Role-Based Access Control (RBAC) |
| Session Security | Secure cookies (HttpOnly, SameSite) |

### Input Validation

| Control | Implementation |
|---------|----------------|
| Parameter Validation | `app/security/param_validation.py` |
| Query String Protection | `app/security/query_string_protection.py` |
| Path Traversal Prevention | `app/security/safe_path.py` |
| URL Safety | `app/security/url_safety.py` |

### Output Encoding

| Control | Implementation |
|---------|----------------|
| Error Messages | Generic user messages, server-side logging |
| Log Forging Prevention | `app/security/log_sanitizer.py` |
| Template Security | All paths hardcoded, SRI for CDN assets |

### HTTP Security Headers

| Header | Value |
|--------|-------|
| Content-Security-Policy | Nonce-based script/style policies |
| X-Content-Type-Options | nosniff |
| X-Frame-Options | SAMEORIGIN |
| Strict-Transport-Security | max-age=31536000; includeSubDomains |

---

## Reporting Security Issues

If you discover a security vulnerability in DMIS:

1. **Do NOT** create a public GitHub issue
2. Contact the ODPEM IT Security team directly
3. Provide:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested remediation (if any)

### Response Timeline

| Severity | Initial Response | Resolution Target |
|----------|------------------|-------------------|
| Critical | 4 hours | 24 hours |
| High | 24 hours | 72 hours |
| Medium | 72 hours | 2 weeks |
| Low | 1 week | Next release |

---

## Additional Resources

- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Semgrep Documentation](https://semgrep.dev/docs/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/latest/security/)

---

*Last Updated: December 2025*

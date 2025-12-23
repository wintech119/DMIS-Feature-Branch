# DMIS - Disaster Management Information System

## Overview
DMIS (Disaster Management Information System) is a web-based platform for the Government of Jamaica's ODPEM, designed to manage the entire lifecycle of disaster relief supplies. Its core purpose is to provide a modern, efficient, and user-friendly solution for disaster preparedness and response. Key capabilities include inventory tracking, donation management, relief request processing, and distribution across multiple warehouses, all while ensuring compliance with government processes and supporting disaster event coordination and supply allocation. The system emphasizes security, robust user administration with Role-Based Access Control (RBAC), inventory transfers, location tracking, analytics, and reporting.

## User Preferences
- **Communication style**: Simple, everyday language.
- **UI/UX Requirements**:
  - All pages MUST have consistent look and feel with Relief Package preparation pages
  - Modern, polished design with summary cards, filter tabs, and clean layouts
  - Easy to use and user-friendly across all features
  - Consistent navigation patterns throughout the application

## System Architecture
The application employs a modular blueprint architecture with a database-first approach, built upon a pre-existing ODPEM `aidmgmt-3.sql` schema.

### Technology Stack
- **Backend**: Python 3.11, Flask 3.0.3
- **Database ORM**: SQLAlchemy 2.0.32 with Flask-SQLAlchemy
- **Authentication**: Flask-Login 0.6.3 with Werkzeug
- **Frontend**: Server-side rendering with Jinja2, Bootstrap 5.3.3, Bootstrap Icons
- **Data Processing**: Pandas 2.2.2

### System Design
- **UI/UX Design**: Consistent modern UI, comprehensive design system, shared Jinja2 components, GOJ branding, accessibility (WCAG 2.1 AA), and standardized workflow patterns. Features role-specific dashboards and complete management modules with CRUD, validation, and optimistic locking.
- **Notification System**: Real-time in-app notifications with badge counters, offcanvas panels, deep-linking, read/unread tracking, and bulk operations using CSRF protection.
- **Donation Processing**: Manages full workflow for donations, including intake, verification, batch-level tracking, expiry dates, and integration with warehouse inventory. Supports document uploads and robust validation.
- **Database Architecture**: Based on a 40-table ODPEM schema, ensuring data consistency, auditability, precision, and optimistic locking. Includes an enhanced `public.user` table, a new `itembatch` table (FEFO/FIFO), `itemcostdef` for cost types, `donation_doc` for document attachments, and composite primary keys.
- **Data Flow Patterns**: Supports end-to-end AIDMGMT Relief Workflow, role-based dashboards, two-tier inventory management, eligibility approval, and package fulfillment with batch-level editing.
- **Role-Based Access Control (RBAC)**: Centralized feature registry, dynamic navigation, security decorators, smart routing, and a defined role hierarchy. Features secure user management with role assignment restrictions and both client-side and server-side validation. Role groups defined: `EXECUTIVE_ROLES`, `LOGISTICS_ROLES`, `AGENCY_ROLES`.
- **Security Features**: Strict nonce-based Content Security Policy (CSP), comprehensive Flask-WTF Cross-Site Request Forgery (CSRF) Protection, secure cookie configuration, Subresource Integrity (SRI) for CDN assets, global no-cache headers, HTTP header sanitization, production-safe error handling, Log Forging prevention, Client Dangerous File Inclusion prevention, email obfuscation, query string protection, open redirect protection, and robust login authentication.
- **API Security (OWASP API Top 10)**: Flask-Limiter rate limiting on all high-risk endpoints. CORS domain allowlisting for ODPEM/JAMICTA subdomains with credential support. SafeApiClient utility for external API consumption. Rate limit headers for client-side handling.
- **Timezone Standardization**: All datetime operations and user-facing displays use Jamaica Standard Time (UTC-05:00).
- **Key Features**: Universal visibility for approved relief requests, accurate inventory validation, batch-level reservation synchronization for draft packages, and automatic inventory table updates on dispatch. Relief package cancellation includes full reservation rollback using optimistic locking and transactional integrity. Implements robust relief request status management. Relief requests are restricted to GOODS items only.
- **Relief Package Analytics Dashboard**: Executive-level analytics for dispatched relief packages (status 'D' and 'R'). Shows KPIs and interactive Chart.js charts. Accessible to DG, Deputy DG, Director PEOD, and Logistics Manager roles.
- **Aid Movement Dashboard**: Read-only analytics dashboard showing aid received, issued, and in-store across warehouses. Features KPIs, filterable table with item search, warehouse selection, movement type filter, and date range filters. Accessible to DG, Deputy DG, Director PEOD, and Logistics Manager roles.
- **Item Distribution Dashboard**: Sub-dashboard under Aid Movement for drilling down into a specific item's distribution across warehouses. Features category filter, item selection, warehouse filter, movement type filter, date range filters, summary KPIs, and per-warehouse breakdown table. Accessible to DG, Deputy DG, Director PEOD, and Logistics Manager roles.
- **Funds Donations Report**: Read-only report for ODPEM Executives showing all FUNDS-type donations. Displays details, filters, and pagination.
- **Currency Conversion Service**: Cached exchange rate service for converting foreign currencies to JMD. Uses a `currency_rate` table for caching. External API integration is currently disabled; system operates with manual/cached rates.
- **Dynamic GOODS/FUNDS Donation Workflow**: Donation form dynamically adapts based on item category type (GOODS/FUNDS) via an API endpoint, automatically setting donation type and controlling field editability.
- **Donation Validation Rules**: Total Donation Value validated against computed sum of line items (0.01 JMD tolerance). Document uploads require `UPLOAD_FOLDER` configuration. FUNDS items enforce quantity = 1.00.
- **Donation Intake Two-Stage Workflow**:
    - **Workflow A (Entry)**: LOGISTICS_OFFICER creates/edits intakes (draft or submitted for verification). No inventory/batch updates.
    - **Workflow B (Verification)**: LOGISTICS_MANAGER reviews submitted intakes, adjusts quantities, and verifies. Status changes to 'V', `ItemBatch` records and `Inventory` totals are updated, and `Donation` status changes to 'P' (Processed). All operations are atomic with optimistic locking.
- **Relief Package Dispatch Workflow (Workflow C)**: LM Submit for Dispatch - Final dispatch operation when Logistics Manager submits a package:
    1. Undo LO reservations.
    2. Overwrite `reliefpkg_item` with LM's final allocation plan.
    3. Deplete usable stock in `itembatch.usable_qty` and `inventory.usable_qty`.
    4. Update `reliefpkg` header status to 'D' (Dispatched).
    5. Update `reliefrqst_item.issue_qty` with actual dispatched quantities.
    All operations are atomic with optimistic locking and robust error handling.
- **Last-Mile Distribution Foundation**: Database foundation for HSA warehouse-to-beneficiary distribution, including custodian classification, HSA master table, warehouse tiering, beneficiary table, and last-mile distribution tables. Intake is restricted for specific warehouse tiers.
- **HSA CRUD Interface**: Complete CRUD for Humanitarian Service Agencies with search/filter, status toggle, linked custodian selection, and optimistic locking. Accessible to CUSTODIAN role.
- **Beneficiary CRUD Interface**: Complete CRUD for beneficiaries (INDIVIDUAL, SHELTER types) with search/filter by type/HSA, location tracking, contact info, and HSA registration linkage. Accessible to CUSTODIAN role.

## External Dependencies

### Required Database
- **PostgreSQL 16+** (production) with `citext` extension.
- **SQLite3** (development fallback).

### Python Packages
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-Limiter
- SQLAlchemy
- psycopg2-binary
- Werkzeug
- pandas
- python-dotenv
- Flask-WTF
- requests

### Frontend CDN Resources
- Bootstrap 5.3.3 CSS/JS
- Bootstrap Icons 1.11.3
- Flatpickr

### DevSecOps Tools
- **Bandit** - Python security linter
- **Semgrep** - Multi-language SAST scanner
- **pip-audit** - Python dependency vulnerability scanner
- **safety** - Python dependency checker
- **SAST Script** - `scripts/run_sast.sh`
- **Dependency Script** - `scripts/run_dep_scan.sh`
- **GitHub Actions** - CI/CD integration for security scans

### Configuration & Deployment
- **Configuration Module** - `settings.py` with environment-driven settings
- **Environment Template** - `.env.example`
- **NGINX Template** - `deploy/nginx.conf.example`
- **Environment Variables**: `DMIS_SECRET_KEY`, `DMIS_DATABASE_URL`, `DMIS_UPLOAD_FOLDER`, etc.
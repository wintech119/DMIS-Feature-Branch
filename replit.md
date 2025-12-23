# DMIS - Disaster Management Information System

## Overview
DMIS (Disaster Management Information System) is a web-based platform for the Government of Jamaica's ODPEM, designed to manage the entire lifecycle of disaster relief supplies. Its core purpose is to provide a modern, efficient, and user-friendly solution for disaster preparedness and response. Key capabilities include inventory tracking, donation management, relief request processing, and distribution across multiple warehouses, ensuring compliance with government processes and supporting disaster event coordination and supply allocation. The system emphasizes security, robust user administration with Role-Based Access Control (RBAC), inventory transfers, location tracking, analytics, and reporting.

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
- **Donation Processing**: Manages full workflow for donations (intake, verification, batch-level tracking, expiry dates), integrates with warehouse inventory, supports document uploads, and robust validation. Dynamic form adaptation based on item category (GOODS/FUNDS) via API.
- **Database Architecture**: Based on a 40-table ODPEM schema, ensuring data consistency, auditability, precision, and optimistic locking. Includes `public.user`, `itembatch`, `itemcostdef`, and `donation_doc` tables.
- **Data Flow Patterns**: Supports end-to-end AIDMGMT Relief Workflow, role-based dashboards, two-tier inventory management, eligibility approval, and package fulfillment with batch-level editing.
- **Role-Based Access Control (RBAC)**: Centralized feature registry, dynamic navigation, security decorators, smart routing, and a defined role hierarchy. Secure user management with role assignment restrictions and both client-side and server-side validation. Role groups include `EXECUTIVE_ROLES`, `LOGISTICS_ROLES`, `AGENCY_ROLES`.
- **Security Features**: Strict nonce-based Content Security Policy (CSP), Flask-WTF Cross-Site Request Forgery (CSRF) Protection, secure cookie configuration, Subresource Integrity (SRI), global no-cache headers, HTTP header sanitization, production-safe error handling, Log Forging prevention, Client Dangerous File Inclusion prevention, email obfuscation, query string protection, open redirect protection, and robust login authentication. Flask-Limiter rate limiting applied to all high-risk endpoints.
- **Timezone Standardization**: All datetime operations, database timestamps, audit trails, and user-facing displays use Jamaica Standard Time (UTC-05:00).
- **Key Features**: Universal visibility for approved relief requests, accurate inventory validation, batch-level reservation synchronization for draft packages, automatic inventory table updates on dispatch. Relief package cancellation includes full reservation rollback. Relief requests are restricted to GOODS items only.
- **Dashboards**:
    - **Relief Package Analytics Dashboard**: Executive-level analytics for dispatched relief packages (status 'D' and 'R'), showing KPIs and interactive charts.
    - **Aid Movement Dashboard**: Read-only analytics showing aid received, issued, and in-store across warehouses, with filtering capabilities.
    - **Item Distribution Dashboard**: Sub-dashboard for drilling down into specific item distribution across warehouses.
- **Funds Donations Report**: Read-only report for ODPEM Executives showing FUNDS-type donations with filtering and pagination.
- **Currency Conversion Service**: Cached exchange rate service for converting foreign currencies to JMD using a `currency_rate` table. Designed for integration with future API providers but currently operates with manual/cached rates.
- **Donation Workflow**: Two-stage workflow: Workflow A for LOGISTICS_OFFICER (entry, draft/submitted for verification), and Workflow B for LOGISTICS_MANAGER (verification, batch/inventory updates, status change to 'V').
- **Relief Package Dispatch Workflow**: When a Logistics Manager submits a package, `dispatch_service.py` handles the core algorithm: undo LO reservations, overwrite allocations, deplete usable stock, update package status to 'D', and update issued quantities. All operations are atomic with optimistic locking.
- **Last-Mile Distribution Foundation**: Database foundation for HSA warehouse-to-beneficiary distribution, including `custodian.custodian_kind`, `public.hsa`, `warehouse.tier_code`, `public.beneficiary`, and `lastmile_distribution` tables. Intake restrictions apply to warehouse tiers.
- **Beneficiary CRUD Interface**: Management interface for beneficiary registration (INDIVIDUAL/SHELTER types) with list, create, edit, view routes, and access control for LOGISTICS_MANAGER and LOGISTICS_OFFICER roles.

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
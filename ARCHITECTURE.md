# Phase 1 architecture

MM Electricals is a **local-first** desktop shop system. Phase 1 delivers the skeleton only: data model, Django API, SQLite safety, backup service types, and a premium React/Tauri shell.

## 1. Architecture summary

```
React (Vite + TypeScript)
  → HTTP /api/v1/  (Vite proxy or Tauri window)
  → Django REST Framework (thin views)
  → Domain services (transactions, audit)
  → Django ORM + migrations
  → SQLite (WAL, foreign keys)
```

- React never opens the database file.
- Calculations and stock changes belong on the server.
- Domain apps: `core`, `products`, `inventory`, `vendors`, `customers`, `purchases`, plus empty packages for `sales`, `payments`, `expenses`, `analytics`, `reports`.
- Deviation from the brief: Django lives under `backend/` with `config/` as the project package (standard Django layout). Tauri lives under `desktop/src-tauri/` so the frontend folder stays a normal Vite app.

Python runtime: **`~/.virtualenvs/shopmanager`** (Python 3.12).

## 2. Directory structure

```
backend/                 Django project (manage.py)
  apps/                 Domain packages
  config/               Settings and root URLs
  data/                 SQLite + backups (gitignored)
  tests/                pytest suite
frontend/               Vite + React + TypeScript + Tailwind
desktop/src-tauri/      Tauri 2 shell
phases/                 Phase prompts (not runtime code)
```

## 3. Database model summary

| Area | Models |
| --- | --- |
| Core | `ApplicationSettings` (singleton), `AuditLog` (append-only) |
| Products | `Category`, `Subcategory`, `Brand`, `Unit`, `Product`, `ProductAlias`, `ProductVendor` |
| Vendors | `Vendor` |
| Customers | `CustomerType` (extensible), `Customer` |
| Inventory | `InventoryBatch` (historical lot pricing + remaining qty), `StockMovement` |
| Purchases | `Purchase`, `PurchaseItem` (frozen purchase-time prices) |

Batches are never overwritten when a new lot arrives. `InventoryService.latest_previous_batch` exists for later “previous batch detected” UI. Stock quantity changes must go through `InventoryService.apply_movement`.

## 4. API structure

Base: **`/api/v1/`**

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health/` | Process + SQLite integrity / journal mode |
| GET | `/version/` | App name, version, API version |
| GET/PATCH | `/settings/` | Shop-wide settings singleton |
| CRUD* | `/categories/`, `/subcategories/`, `/brands/`, `/units/`, `/products/`, `/product-vendors/` | Catalog |
| CRUD* | `/vendors/`, `/customers/`, `/customer-types/` | Parties |
| CRUD* | `/batches/` | Lots; `GET /batches/previous/?product=` |
| GET | `/stock-movements/` | Read-only movements |

\*HTTP: GET, POST, PATCH (no hard DELETE on master/financial-style rows in Phase 1).

Conventions: `?page=&page_size=`, `?search=`, django-filter fields. Errors: `{ "error": { "code", "message", "details" } }`.

## 5–8. Files, commands, tests

Recorded in the Phase 1 completion notes in the README workflow: `makemigrations`, `migrate`, `pytest`, `npm install`, `npm run build`.

## 9. Known limitations (Phase 1)

- No purchase/sale posting UI or complete invoice workflow.
- No packaged Windows installer; Tauri needs Rust (`rustup`) on the build machine.
- Auth is open local API (loopback). Multi-user comes later; `AuditLog.actor` is a string.
- Backup **service** can copy SQLite and write CSV folders; no scheduler UI.
- Owner pricing recommendations are not implemented (schema only).
- End users still need a developer machine to run Phase 1; packaging is a later phase.

## Phase 2 — Inventory, batches, Smart Finder

Phase 2 extends the Phase 1 skeleton. React still never opens SQLite.

**Search:** `ProductSearchService` tokenises the query. Each token must match name, SKU, barcode, brand, category, specification, HSN, aliases, tags, or vendor SKU. Results are annotated with on-hand qty and the newest open batch. The browser never downloads the catalog.

**Batches:** `InventoryService.create_batch` always inserts a new lot. Previous lots are frozen. If a prior lot exists, `pricing_confirmed` is required. Modes: `PREVIOUS`, `COPY_EDIT`, `NEW`. Safe selling price and max discount are stored on the lot; the server never invents them.

**Movements:** `apply_movement` records `quantity_before` / `quantity_after` in the same transaction as the qty change.

**Valuation:** `ValuationService` defaults to **FIFO**. Weighted average is registered but not the shop default (`ApplicationSettings.inventory_valuation_method`).

**APIs added:** `GET /products/finder/`, `GET /products/{id}/card/`, `POST /batches/receive/`, `GET /batches/previous/`, `POST /stock-movements/adjust/`, tag CRUD.

**UI:** Inventory list, product card, receive-lot form with previous-batch banner, stock adjust, global Smart Finder (keyboard ↑↓ Enter).

## Phase 3 — Purchases, sales, ledgers

Stock still moves only through `InventoryService`. Invoice numbers come from `DocumentNumberService` (prefix + financial year + sequence). React never allocates numbers.

**Purchase posting** (`PurchaseService.create_purchase`): validate → header → items → new batches → stock movements → optional vendor payment → vendor ledger credit. Rollback on any failure. Previous lots are never overwritten.

**Sale posting** (`SaleService.create_sale`): FIFO `allocate_fifo` + `apply_movement` per lot line, exclusive GST, payment, customer ledger debit. Below-safe-price warns (`SAFE_PRICE_WARNING`) unless overridden; hard-block only if `enforce_safe_selling_price`.

**Returns** create new documents; originals stay. Payments write `Payment` + `LedgerEntry`. Customer/vendor `current_balance` is a cache.

**APIs:** `POST/GET /purchases/`, `POST /purchases/{id}/returns/`, `POST/GET /sales/`, `GET /sales/{id}/invoice/`, `POST /sales/{id}/returns/`, `POST/GET /payments/`, `GET /customers/{id}/ledger/`, `GET /vendors/{id}/ledger/`.

**UI:** Quick Sell, purchases, customers, vendors, payments.

## Phase 4 — Analytics and owner dashboard

React never aggregates shop history. `AnalyticsService` / `InsightService` return JSON; the UI renders it. Cache TTL is 45s (dashboard 20s) on `locmem`.

**Calculation definitions**

- Revenue (ex GST): `quantity * unit_price - discount_amount` on `SaleItem`.
- COGS: `quantity * batch_cost` (sale-line snapshot), falling back to `InventoryBatch.purchase_cost`. Never current product cost.
- Gross profit: revenue − COGS. Margin %: profit / revenue.
- Stock value (FIFO): sum of `remaining_quantity * purchase_cost` on lots with remaining qty.
- Sales growth: current date window vs the immediately previous equal-length window.
- Insights are facts from stored rows (low stock, dead stock, receivables, brand profit share, lot cost increases). No forecasts.

**Aggregation strategy**

- Date filters: `date_from` / `date_to` (default last 30 days). Optional `category_id`, `brand_id`, `vendor_id`, `customer_id`, `product_id`.
- Daily series groups on `invoice_date`. Week/month/year use Trunc*; SQLite failures return an empty series.
- CSV: `GET /api/v1/analytics/export/<report>/`. Print/PDF: browser print.

**HTTP:** `/api/v1/analytics/dashboard|sales|profit|inventory|purchases|vendors|discounts|customers|expenses|batches|insights/`, `GET /analytics/products/<id>/price-history/`.

**UI:** Dashboard, Analytics (tabs + CSV + print), Expenses, Reports, product price-history tab.

**Tests:** `backend/tests/test_phase4.py` — sales/profit vs known lots, date filters, FIFO remainder, vendor comparison, discounts, expenses + CSV.

**Limitations:** Locmem cache is per-process. TruncWeek/Month/Year may be empty on SQLite. Gross sales on the sales tab uses invoice `grand_total` (includes GST); profit tab uses line revenue ex-GST. PDF is print-to-PDF, not a server renderer.

## Phase 5 — Production hardening

Operator data lives under `%LOCALAPPDATA%\MMElectricals` on Windows (`backend/data` in development). SQLite is never stored next to the installer payload.

**Backup:** `SnapshotBackupService` writes timestamped folders (`database/`, `csv/`, `metadata.json`), validates `PRAGMA integrity_check`, and prunes by `backup_retention_count`. Restore always takes a safety snapshot first and rolls back if integrity fails.

**Health:** `HealthService.diagnose` reports missing files, corruption, pending migrations, and a recovery sentence (no stack traces).

**Packaging:** PyInstaller `backend/packaging/launch_api.py` + Tauri NSIS installer. API binds `127.0.0.1` only (`LoopbackOnlyMiddleware`). Commands: `backup_database`, `restore_database`, `run_scheduled_backup`, `safe_upgrade`.

**Printing:** HTML A4/thermal from `InvoicePrintService`; OS printer dialog.

**Docs:** `docs/PRODUCTION.md`. Tests: `backend/tests/test_phase5.py`.


# Ivanka marketplace

A runnable, standalone Django + Django REST Framework marketplace with a responsive single-page frontend. The landing page is ecommerce. The `hiring` application retains the `hiring.CustomUser` identity and provides business recruitment. `store` owns catalog, seller accounts, courier accounts, orders, payments and messaging.

This is an initial marketplace implementation, not a complete Takealot-scale operations platform. See `docs/OPERATIONS.md` for external setup, implemented boundaries and the validation record.

## Start on Windows

Open a terminal in this extracted folder (the one containing `manage.py`):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py bootstrap_store
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

If PowerShell activation is blocked, use `.venv\Scripts\python.exe` instead of `python` for the remaining commands. You do not need to change system execution policy.

Open **http://127.0.0.1:8000/**. Administration is **http://127.0.0.1:8000/admin/**. No default passwords are shipped. `seed_demo` creates an illustrative seller with an unusable password; create your own account and store to test seller flows. For a buyer, register through the account icon.

## Start on Linux / macOS

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py bootstrap_store
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

`bootstrap_store` is safe for a blank real database: it creates the base currency and gateway records without demo products or foreign exchange rates. `seed_demo` is optional and idempotent; it adds original product illustrations, demo listings, an illustrative vacancy, coupon HELLO10 and **example exchange rates**. Replace or disable example rates before taking real orders.

## What you can do

- Browse/search/filter catalog, inspect variants and galleries, save products.
- Register/login/reset password; choose a black or white interface.
- Select enabled currencies; server calculates converted prices. Rates and order currency are frozen at checkout. Orders stay in their original currency when the viewer changes currency.
- Upload product images: validated, metadata stripped, oriented, centred on a neutral 1200 × 1200 canvas, converted to WebP. Optional local background removal is described below.
- Sellers register for approval, edit listings, upload images and manage SKU prices/stock. Checkout groups products into an order for each seller.
- Buyers save addresses/GPS, apply coupons, check out, choose cash or Yoco, message sellers, track deliveries and submit verified reviews/return requests after delivery.
- Sellers progress orders from confirmed → packing → shipped. Packing opens a delivery job.
- Approved couriers claim jobs or bid; sellers can accept bids within the prepaid shipping budget. Courier owners assign drivers provisioned by staff. Drivers share foreground GPS and advance pickup/transit/delivery status.
- Recruitment: approved businesses submit jobs; staff publishes; users apply and view their application status.
- Admin controls approvals, categories, currencies, coupons, recruitment and return processing. Financial records are read-only.

## Currency changes

Use **Admin → Store currencies** to enable currencies and edit rates. Rate means **units of the selected currency per 1 catalog currency unit**. For example, with a ZAR catalog and an illustrative USD rate of 0.05, ZAR 100 becomes USD 5.00. This example is not a current market quote.

The catalog base is `CATALOG_CURRENCY=ZAR` in `.env`. Select the base **before entering real prices**; changing this variable does not convert existing catalog prices. To change an established catalog base, migrate/reprice products and shipping fees and recompute rates as an explicit business operation. Historical orders and ledger rows retain their currency.

Only two-decimal supported currencies are exposed by the admin form. JPY/KWD and other minor-unit formats need an explicit money-format/payment extension. No automatic live-rate provider is configured. Foreign-currency cash availability must fit the merchant's actual cash collection arrangements. The supplied Yoco adapter supports **ZAR only**; non-ZAR online checkout needs another adapter. No credential from OppoGlobe is copied.

## Images and one background

Every uploaded image gets the same #f4f4f2 square canvas, spacing and encoding. Transparent cutouts therefore have a fully consistent background in both themes. When automatic removal is off, ordinary opaque photos are rejected with a clear message: sellers must upload a transparent PNG/WebP product cutout. This prevents publishing a mixture of photographic backgrounds. Enable removal to accept ordinary JPG/PNG/WebP photographs. Resizing alone cannot remove a background.

For optional automatic cutouts:

```bash
python -m pip install "rembg[cpu]"
```

Set `PRODUCT_REMOVE_BACKGROUND=true`. Provision/cache the rembg model before deployment (first use can download it). This optional mode was not exercised in this build. Failed removal rejects the upload rather than publishing an inconsistent image. Background removal quality depends on the image; inspect difficult edges. For high-volume use, move this processing to a job queue. Existing uploads are not reprocessed by changing the option.

## Payments / Google Maps / deployment

Read `docs/OPERATIONS.md` and `docs/API.md`. Yoco uses server-side checkout and verified signed webhooks, not the browser success redirect, to confirm payment. Google Maps keys are separated into browser and server keys.

For meaningful multi-buyer concurrency use PostgreSQL; SQLite is for local exploration. Migrations are included. Run tests with:

```bash
python manage.py test store
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Existing OppoGlobe project

This archive is a **new, isolated Ivanka project**, not a patch to your current database. Your uploaded hiring views depended on realestate, notifications, carwash and other files that were not provided. The new lean hiring implementation preserves the custom-user model name and basic fields, but does not reproduce those unrelated modules or existing migrations. **Do not overwrite your live `hiring` app or run this initial hiring migration against an existing database.**

For integrating into an existing mother project, see `docs/INTEGRATION.md`. Keep the existing user model and migration history; integrate the `store` app first in a staging database. The user-sharing design is `settings.AUTH_USER_MODEL`, not direct dependencies on OppoGlobe models.

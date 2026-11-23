# Job Recruitment Website

Full-stack job board built with Python (Flask) and SQLite. Built by **WIC Technologies**.

## What is inside

**Public website**
- Home page with animated hero, live stats, categories and latest jobs
- Job search with filters (keyword, category, location, type) and pagination
- Job details page with apply form and CV upload (PDF, DOC, DOCX)
- "Submit CV" page for people who cannot find a matching job
- Employers page: companies send vacancy requests
- About and Contact pages, WhatsApp floating button
- Fully responsive (phone, tablet, laptop, large screens)

**Owner-only admin** (`/admin`)
- Dashboard with counts and latest applications
- Post, edit, feature, close and delete jobs
- View applications, change status (new, reviewed, shortlisted, rejected), download CVs
- Employer requests and contact messages
- Settings: company name, tagline, email, phone, WhatsApp, address, social links, logo upload, change password

CVs are stored privately in `instance/cv_uploads` and can only be downloaded by the logged-in admin.

## Run it on your computer

```bash
cd job-recruitment-site
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac / Linux
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

Admin: http://127.0.0.1:5000/admin

On first run an admin account is created:

- Username: `admin`
- Password: `ChangeMe@2026`

**Log in and change the password immediately** (Admin > Settings > Change admin password).
You can also choose your own before the first run:

```bash
set ADMIN_USER=owner
set ADMIN_PASS=YourStrongPassword
python app.py
```

## Make it the client's own

1. Log in to `/admin` > **Settings** and enter the real company name, tagline, email, phone, WhatsApp, address and logo.
2. Go to **Jobs** and delete the 8 demo jobs, then post real ones.

## Deploying

Any host that runs Python works (PythonAnywhere, Render, Railway, a VPS).

```bash
gunicorn app:app
```

Production checklist:
- Set a `SECRET_KEY` environment variable (otherwise one is generated and saved in `instance/secret.key`)
- Set `HTTPS=1` once the site runs on https
- Keep the `instance/` folder (database, CVs) backed up and never public

## Folder structure

```
app.py            backend: routes, database, admin, uploads
templates/        HTML pages (admin/ holds the admin pages)
static/css        style.css (website), admin.css (admin)
static/js         main.js (animations, menu, uploads)
instance/         created automatically: site.db, cv_uploads/
```

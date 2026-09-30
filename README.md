# ShopLite — E-commerce Web Application

Full-stack demo store built with Flask, SQLAlchemy, SQLite, Jinja templates, and vanilla CSS.

## Features
- Product catalog with category, description, stock, image, and INR price
- Session-based shopping cart, quantity updates, and demo checkout
- Registration/login with Werkzeug password hashing
- User order history and order status
- Admin product creation/deletion and order status management
- JSON endpoints: `GET /api/products`, authenticated `GET /api/orders`, `GET /api/health`
- Seeded sample products and a development admin account

## Run
From this directory:
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r ../requirements.txt
python app.py
```
Open http://127.0.0.1:5000

Development admin: `admin@shoplite.local` / `Admin123!`
Change this password and use a strong `SECRET_KEY` before deployment. Checkout is simulated; no payment details are collected or processed.

## Database
SQLite file `shop.db` is created automatically. Set `DATABASE_URL` to use PostgreSQL in deployment. Use a persistent disk if deploying SQLite on an ephemeral host.

# 🍽 Kasi Flavour – Full Stack Setup Guide

## Tech Stack
| Layer     | Technology                          |
|-----------|-------------------------------------|
| Backend   | Python · FastAPI · Uvicorn          |
| Database  | MySQL · SQLAlchemy ORM · Alembic    |
| Frontend  | HTML · CSS · Vanilla JavaScript     |
| ML        | scikit-learn · pandas · numpy       |
| Real-time | WebSocket (FastAPI native)          |
| Auth      | JWT (python-jose · passlib/bcrypt)  |
| Cache     | Redis (flash deals · sessions)      |
| Offline   | Service Worker · IndexedDB          |
| Maps      | Leaflet.js (OpenStreetMap)          |

---

## Project Structure
```
kasi-flavour/
├── backend/
│   ├── main.py              ← FastAPI app entry point
│   ├── database.py          ← SQLAlchemy engine + session
│   ├── requirements.txt
│   ├── models/
│   │   └── models.py        ← ORM table definitions (8 tables)
│   ├── schemas/
│   │   └── schemas.py       ← Pydantic request/response models
│   ├── routers/
│   │   ├── auth.py          ← Register / Login / JWT
│   │   ├── users.py         ← User profiles + location
│   │   ├── menus.py         ← Menu items + flash deals
│   │   ├── orders.py        ← Place / track / update orders
│   │   ├── tracking.py      ← WebSocket GPS tracking
│   │   └── recommend.py     ← ML recommendation endpoint
│   └── services/            ← (add business logic here)
│
├── frontend/
│   ├── pages/
│   │   ├── index.html       ← Customer browse + order
│   │   ├── seller.html      ← Cook dashboard
│   │   └── track.html       ← Live GPS tracking map
│   ├── css/
│   │   └── main.css         ← Warm food-app palette
│   ├── js/
│   │   ├── api.js           ← Centralised API client
│   │   ├── cart.js          ← Cart state + order placement
│   │   └── menus.js         ← Menu rendering + flash timer
│   └── service-worker.js    ← Offline mode + background sync
│
└── ml/
    ├── recommend.py         ← 3-signal recommendation engine
    ├── train.py             ← Build + save model.pkl
    └── notebooks/           ← (Jupyter EDA notebooks here)
```

---

## Quick Start

### 1. MySQL – Create database
```sql
CREATE DATABASE kasi_flavour CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'kasi'@'localhost' IDENTIFIED BY 'yourpassword';
GRANT ALL PRIVILEGES ON kasi_flavour.* TO 'kasi'@'localhost';
FLUSH PRIVILEGES;
```

### 2. Backend setup
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="mysql+pymysql://kasi:yourpassword@localhost:3306/kasi_flavour"
export SECRET_KEY="change-this-to-a-long-random-string"

# Start the server (tables auto-created on first run)
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 3. Train the ML model
```bash
cd ml
python train.py
# → saves model.pkl
```

### 4. Frontend
Open `frontend/pages/index.html` in a browser, or serve with:
```bash
cd frontend
python -m http.server 5500
# Open http://localhost:5500/pages/index.html
```

---

## Key API Endpoints
| Method | Path                       | Description                     |
|--------|----------------------------|---------------------------------|
| POST   | /api/auth/register         | Create account                  |
| POST   | /api/auth/login            | Login → JWT token               |
| GET    | /api/menus?flash=true      | Flash deals                     |
| GET    | /api/menus?kasi=Soweto     | Filter by neighbourhood         |
| POST   | /api/orders                | Place an order                  |
| PATCH  | /api/orders/{id}/status    | Cook/driver updates status      |
| WS     | /api/track/driver/{id}     | Driver streams GPS location     |
| WS     | /api/track/order/{id}      | Customer receives live location |
| POST   | /api/recommend             | Get top-5 AI meal picks         |

---

## Cook Rating DNA Badges
Badges are stored as comma-separated strings on the `cooks.badges` column.
The review system reads `tags` from reviews to compute and assign badges:

| Badge        | Trigger                              |
|--------------|--------------------------------------|
| 🌶 Spicy Queen | ≥5 "spicy" tags in reviews          |
| 👑 Portion King | ≥5 "generous" tags in reviews      |
| ⚡ Speed Demon  | Average prep time < 20 min          |
| ❤️ Community Fave | Rating ≥ 4.8 with ≥10 reviews    |

---

## Offline Mode
The service worker caches the app shell on first load. When offline:
- Customers can browse the cached menu
- Orders are queued in IndexedDB and synced automatically when back online (Background Sync API)
- Tracking page shows last known driver position

---

## Environment Variables
| Variable       | Default                                | Description         |
|----------------|----------------------------------------|---------------------|
| `DATABASE_URL` | mysql+pymysql://root:password@...      | MySQL connection    |
| `SECRET_KEY`   | kasi-flavour-secret-change-in-prod     | JWT signing key     |
| `REDIS_URL`    | redis://localhost:6379                 | Redis connection    |

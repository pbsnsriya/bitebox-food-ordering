# BiteBox — Food Ordering System

A React + Flask restaurant ordering application. The frontend is deliberately kept straightforward: components are small, names are descriptive, and the data flow is easy to follow instead of hiding everything behind abstractions.

## Project structure

```text
food-ordering-app/
├── src/
│   ├── main.jsx
│   └── styles.css
├── backend/
│   ├── app.py
│   └── requirements.txt
├── index.html
├── package.json
└── README.md
```

## Frontend

```bash
npm install
npm run dev
```

The React app expects Flask at `http://localhost:5000`.

## Backend

Open a second terminal:

```bash
cd backend
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
python app.py
```

## Authentication

Customer accounts are created through `/api/auth/signup` and login uses `/api/auth/login`. Passwords are stored as hashes and protected endpoints use JWT access tokens.

Set `JWT_SECRET_KEY` in the environment before running the backend in a persistent environment. When it is unset, the backend generates a temporary key for local development, which invalidates tokens whenever the process restarts.

For local testing, an admin account is seeded automatically:

- Email: `admin@bitebox.local`
- Password: `admin123`

Change the JWT secret and admin credentials before using this outside local development.

## AI-style menu search

The menu search is not just a keyword `in` check. It performs:

- basic tokenisation and lemmatisation
- small restaurant-specific synonym mapping (`veg` → `vegetarian`, `hot` → `spicy`)
- TF-IDF with unigrams and bigrams
- cosine similarity ranking
- budget extraction for phrases such as `under 200`
- simple negative intent handling for `not`, `without`, `avoid`, etc.
- a small tag-match boost

This keeps the implementation understandable while giving noticeably better results than a plain keyword matcher. The NLP layer can later be replaced by an embedding model if the project needs more semantic search.

## Main API endpoints

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/menu`
- `GET /api/menu/search?q=...`
- `POST /api/orders`
- `GET /api/orders/my`
- `GET /api/admin/orders`
- `PATCH /api/admin/orders/<id>`
- `GET /api/admin/dashboard`
- `GET /api/health`

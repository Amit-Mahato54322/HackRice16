## CREDIT PICK ##
<p>Smart credit card recommendation system</p>

## Backend setup (FastAPI)

The backend lives in `/backend`. It currently serves frozen mock fixtures
(`backend/mock/*.json`) for auth, dashboard, cards, and recommend — no
Postgres connection is required to boot it.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # fill in Nessie/Gemini/ElevenLabs/VectorMint keys as needed
uvicorn app.main:app --reload
```

Once running:

- Health check: `http://localhost:8000/health` → `{"status": "ok"}`
- Interactive API docs (Swagger UI): `http://localhost:8000/docs`

Table creation is not wired into app startup — `create_tables()` in
`backend/app/db.py` is available for a future seed script once Postgres is
actually in the loop.

See `docs/PLAN.md` for architecture, data model, and the full milestone list.

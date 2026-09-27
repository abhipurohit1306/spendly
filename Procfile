web: python -c "from database.db import init_db, seed_db; init_db(); seed_db()" && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2

import csv
import os
import sys

from peewee import chunked

# Bootstrap the app so models + DB are wired up
from app import create_app

app = create_app()

from app.database import db
from app.models import Event, Url, User

USERS_CSV  = os.getenv("USERS_CSV",  "users.csv")
URLS_CSV   = os.getenv("URLS_CSV",   "urls.csv")
EVENTS_CSV = os.getenv("EVENTS_CSV", "events.csv")


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def seed_users(rows):
    data = [
        {
            "id":         int(r["id"]),
            "username":   r["username"],
            "email":      r["email"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    with db.atomic():
        for batch in chunked(data, 100):
            User.insert_many(batch).on_conflict_ignore().execute()
    print(f"  users:  {len(data)} rows")


def seed_urls(rows):
    # Get all existing user IDs to validate foreign keys
    existing_user_ids = set(u.id for u in User.select(User.id))
    
    data = [
        {
            "id":           int(r["id"]),
            "user_id":      int(r["user_id"]),
            "short_code":   r["short_code"],
            "original_url": r["original_url"],
            "title":        r.get("title") or None,
            "is_active":    r["is_active"].strip().lower() in ("true", "1", "yes"),
            "created_at":   r["created_at"],
            "updated_at":   r["updated_at"],
        }
        for r in rows
        if int(r["user_id"]) in existing_user_ids  # Filter out URLs with non-existent user_ids
    ]
    with db.atomic():
        for batch in chunked(data, 100):
            Url.insert_many(batch).on_conflict_ignore().execute()
    print(f"  urls:   {len(data)} rows")


def seed_events(rows):
    # Get all existing URL and User IDs to validate foreign keys
    existing_url_ids = set(u.id for u in Url.select(Url.id))
    existing_user_ids = set(u.id for u in User.select(User.id))
    
    data = [
        {
            "id":         int(r["id"]),
            "url_id":     int(r["url_id"]),
            "user_id":    int(r["user_id"]),
            "event_type": r["event_type"],
            "timestamp":  r["timestamp"],
            "details":    r.get("details") or None,
        }
        for r in rows
        if int(r["url_id"]) in existing_url_ids and int(r["user_id"]) in existing_user_ids  # Filter out events with non-existent foreign keys
    ]
    with db.atomic():
        for batch in chunked(data, 100):
            Event.insert_many(batch).on_conflict_ignore().execute()
    print(f"  events: {len(data)} rows")


def main():
    print("Creating tables …")
    with app.app_context():
        db.create_tables([User, Url, Event], safe=True)

        print("Seeding …")
        seed_users(_read(USERS_CSV))
        seed_urls(_read(URLS_CSV))
        seed_events(_read(EVENTS_CSV))

    print("Done ✓")


if __name__ == "__main__":
    main()
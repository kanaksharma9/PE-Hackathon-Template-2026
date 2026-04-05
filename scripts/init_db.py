# scripts/init_db.py
import psycopg2
from psycopg2 import sql
import os
import getpass

# Try different password options
passwords_to_try = [
    os.environ.get("POSTGRES_PASSWORD", "postgres"),  # From environment variable
    "postgres",  # Default
    "",  # No password
]

connected = False
for password in passwords_to_try:
    try:
        conn = psycopg2.connect(
            host=os.environ.get("DATABASE_HOST", "localhost"),
            port=int(os.environ.get("DATABASE_PORT", 5432)),
            user=os.environ.get("DATABASE_USER", "postgres"),
            password=password
        )
        connected = True
        break
    except psycopg2.OperationalError:
        continue

if not connected:
    # Prompt user for password
    password = getpass.getpass("Enter PostgreSQL password: ")
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password=password
        )
        connected = True
    except Exception as e:
        print(f"Failed to connect: {e}")
        exit(1)

try:
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Fix: CREATE DATABASE uses CREATE, not CREATE IF NOT EXISTS
    cursor.execute("CREATE DATABASE hackathon_db")
    cursor.close()
    conn.close()
    print("Database 'hackathon_db' created successfully!")
except psycopg2.Error as e:
    if "already exists" in str(e):
        print("Database 'hackathon_db' already exists.")
    else:
        print(f"Error: {e}")
except Exception as e:
    print(f"Error: {e}")

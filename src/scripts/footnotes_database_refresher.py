# TO BE IMPLEMENTED
import base64
import os
import sqlite3
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

# Configuration from environment
CLIENT_ID = os.environ.get("CLIENT_ID_PROD")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET_PROD")
BASE_URL = os.environ.get("PROD_API_ENDPOINT", "https://apis.quran.foundation")
AUTH_URL = os.environ.get("PROD_AUTH_ENDPOINT", None)

# 20 is saheeh international
# 95 is abu al ala maududi
TRANSLATION_IDS = [20, 95]
DB_DIR = os.path.join("src", "locked")
DB_PATH = os.path.join(DB_DIR, "footnotes-v1.db")


def get_access_token():
    print("Obtaining access token...")
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: CLIENT_ID_PROD or CLIENT_SECRET_PROD not set in environment.")
        sys.exit(1)

    payload = {"grant_type": "client_credentials", "scope": "content"}
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    if not AUTH_URL:
        print("Error: PROD_AUTH_ENDPOINT not set in environment.")
        sys.exit(1)

    with httpx.Client() as client:
        try:
            response = client.post(
                AUTH_URL,
                data=payload,
                headers=headers,
            )
            response.raise_for_status()
            token = response.json().get("access_token")
            print("Access token obtained successfully.")
            return token
        except httpx.HTTPStatusError as e:
            print(f"Failed to obtain access token: {e}")
            print(f"Response: {e.response.text}")
            sys.exit(1)
        except httpx.RequestError as e:
            print(f"Failed to obtain access token: {e}")
            sys.exit(1)


def init_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expires (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            expires_at_ms INTEGER NOT NULL
        );
    """)

    for resource_id in TRANSLATION_IDS:
        table_name = f"foot_notes_translation_id_{resource_id}"
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verse_id INTEGER NOT NULL,
                foot_note_id INTEGER NOT NULL,
                foot_note_text TEXT NOT NULL
            );
        """)

    expires_at_ms = int((time.time() + 6 * 24 * 60 * 60) * 1000)
    cursor.execute(
        "INSERT OR REPLACE INTO expires (id, expires_at_ms) VALUES (1, ?)",
        (expires_at_ms,),
    )
    conn.commit()
    return conn


def fetch_and_store_all_footnotes(token, conn):
    cursor = conn.cursor()
    headers = {
        "x-auth-token": token,
        "x-client-id": CLIENT_ID,
        "Accept": "application/json",
    }

    # Clean path prefix parsing logic
    api_root = BASE_URL.rstrip("/")
    if "/content/api/v4" not in api_root:
        api_root = f"{api_root}/content/api/v4"

    with httpx.Client(base_url=api_root, headers=headers, timeout=120.0) as client:
        for resource_id in TRANSLATION_IDS:
            table_name = f"foot_notes_translation_id_{resource_id}"
            print(f"\nProcessing Translation ID: {resource_id}...")

            cursor.execute(f"DELETE FROM {table_name}")
            conn.commit()

            endpoint = f"/quran/translations/{resource_id}"

            # Use a single huge page size to pull the entire corpus at once
            params = {"foot_notes": "true", "per_page": 7000, "page": 1}

            try:
                print(" -> Querying bulk payload from server...")
                response = client.get(endpoint, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as e:
                print(f" -> API Error fetching Translation {resource_id}: {e}")
                continue

            translations = data.get("translations", [])
            print(
                f" -> Downloaded {len(translations)} items. Parsing footnotes by sequential index..."
            )

            # Enumerate through the items. index starts at 0, so index + 1 maps to verse_id 1 to 6236
            for idx, item in enumerate(translations):
                calculated_verse_id = idx + 1

                item_footnotes = item.get("foot_notes")
                if not item_footnotes or not isinstance(item_footnotes, dict):
                    continue

                for fn_id, fn_text in item_footnotes.items():
                    try:
                        clean_fn_id = int(fn_id)
                    except ValueError:
                        continue

                    cursor.execute(
                        f"""
                        INSERT INTO {table_name} (verse_id, foot_note_id, foot_note_text)
                        VALUES (?, ?, ?)
                    """,
                        (calculated_verse_id, clean_fn_id, fn_text),
                    )

            conn.commit()
            print(f" -> Completed processing into {table_name}.")


if __name__ == "__main__":
    access_token = get_access_token()
    db_connection = init_database()
    try:
        fetch_and_store_all_footnotes(access_token, db_connection)
        print("\nAll target footnotes have been systematically saved.")
    finally:
        db_connection.close()

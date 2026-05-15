import base64
import os
import sqlite3
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

# Configuration from environment
CLIENT_ID = os.environ.get("CLIENT_ID_PROD")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET_PROD")
BASE_URL = os.environ.get("PROD_API_ENDPOINT", None)
AUTH_URL = os.environ.get("PROD_AUTH_ENDPOINT", None)

DB_DIR = "db"
DB_PATH = os.path.join(DB_DIR, "complete-quran.db")

# Translation target languages and preferred translators/slugs
TARGET_MAPPING = {
    20: {"lang": "en", "translator_name": "Saheeh International"},
    95: {
        "lang": "en",
        "translator_name": "Sayyid Abul Ala Maududi (Tafhim commentary)",
    },
    158: {"lang": "ur", "translator_name": "Bayan-ul-Quran (Dr. Israr Ahmad)"},
    234: {"lang": "ur", "translator_name": "Fatah Muhammad Jalandhari"},
    33: {"lang": "id", "translator_name": "Indonesian Islamic Affairs Ministry"},
}


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


def create_tables(conn):
    print("Creating tables...")
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chapters (
        id INTEGER PRIMARY KEY,
        name_arabic TEXT NOT NULL,
        name_complex TEXT NOT NULL,
        revelation_place TEXT,
        verses_count INTEGER NOT NULL,
        pages INTEGER NOT NULL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verses (
        id INTEGER PRIMARY KEY,
        surah_id INTEGER NOT NULL,
        verse_number INTEGER NOT NULL,
        text_uthmani TEXT NOT NULL,
        text_indopak TEXT NOT NULL,
        verse_key TEXT NOT NULL,
        juz_number INTEGER,
        FOREIGN KEY (surah_id) REFERENCES chapters(id)
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS translations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        verse_id INTEGER NOT NULL,
        language_code TEXT NOT NULL,
        translation_text TEXT NOT NULL,
        translator_name TEXT,
        FOREIGN KEY (verse_id) REFERENCES verses(id)
    )""")

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_translation_lang ON translations (verse_id, language_code)"
    )

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY,
        verse_id INTEGER NOT NULL,
        position INTEGER NOT NULL,
        text_arabic TEXT NOT NULL,
        trans_en TEXT,
        trans_ur TEXT,
        trans_id TEXT,
        audio_key TEXT,
        FOREIGN KEY (verse_id) REFERENCES verses(id)
    )""")

    conn.commit()
    print("Tables created successfully.")


def populate_database():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

    token = get_access_token()
    headers = {
        "x-auth-token": token,
        "x-client-id": CLIENT_ID,
        "Accept": "application/json",
    }

    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)

    # Crucial for SQLite as requested
    # conn.cursor().execute("PRAGMA foreign_keys = ON;")
    # conn.commit()

    trans_ids_str = ",".join(map(str, TARGET_MAPPING.keys()))

    with httpx.Client(timeout=60.0) as client:
        print("Populating chapters...")
        chapters_url = f"{BASE_URL}/chapters"
        resp = client.get(chapters_url, headers=headers)
        resp.raise_for_status()
        chapters = resp.json().get("chapters", [])

        cursor = conn.cursor()
        for ch in chapters:
            cursor.execute(
                """
                INSERT OR REPLACE INTO chapters (
                    id, name_arabic, name_complex, revelation_place, verses_count, pages
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    ch["id"],
                    ch["name_arabic"],
                    ch["name_complex"],
                    ch["revelation_place"],
                    ch["verses_count"],
                    ch["pages"][0],
                ),
            )
        conn.commit()
        print(f"Populated {len(chapters)} chapters.")

        # 3. Fetch and populate Verses, Translations, and Words
        for ch in chapters:
            ch_id = ch["id"]
            print(f"Processing Chapter {ch_id}: {ch['name_complex']}...")

            verses_url = f"{BASE_URL}/verses/by_chapter/{ch_id}"

            # Combined logic:
            # - keep the verse fetch structure from local_translation_generator.py
            # - keep the verse/word insertion logic from local_sqlite_generator.py
            # - add per_page=all as requested
            params = {
                "language": "en",
                "words": "true",
                "translations": trans_ids_str,
                "fields": "id,verse_number,text_uthmani,text_indopak,verse_key,juz_number",
                "per_page": "all",
            }

            resp = client.get(verses_url, headers=headers, params=params)
            resp.raise_for_status()
            verses_data = resp.json().get("verses", [])

            print(f"  Fetching word translations (UR, ID) for chapter {ch_id}...")

            # Urdu word translations
            resp_ur = client.get(
                verses_url,
                headers=headers,
                params={
                    "language": "ur",
                    "words": "true",
                    "per_page": "all",
                },
            )
            resp_ur.raise_for_status()
            verses_ur = resp_ur.json().get("verses", [])

            # Indonesian word translations
            resp_id = client.get(
                verses_url,
                headers=headers,
                params={
                    "language": "id",
                    "words": "true",
                    "per_page": "all",
                },
            )
            resp_id.raise_for_status()
            verses_id = resp_id.json().get("verses", [])

            # Map word translations by verse_key and word position
            ur_word_trans = {}
            for v in verses_ur:
                v_key = v["verse_key"]
                for w in v.get("words", []):
                    ur_word_trans[(v_key, w["position"])] = w.get(
                        "translation", {}
                    ).get("text")

            id_word_trans = {}
            for v in verses_id:
                v_key = v["verse_key"]
                for w in v.get("words", []):
                    id_word_trans[(v_key, w["position"])] = w.get(
                        "translation", {}
                    ).get("text")

            for v in verses_data:
                v_id = v.get("id")
                if not v_id:
                    continue
                v_key = v.get("verse_key")

                # Insert Verse
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO verses (
                        id, surah_id, verse_number, text_uthmani,
                        text_indopak, verse_key, juz_number
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        v_id,
                        ch_id,
                        v.get("verse_number"),
                        v.get("text_uthmani", ""),
                        v.get("text_indopak", ""),
                        v_key,
                        v.get("juz_number"),
                    ),
                )

                # Insert Translations for the current verse only
                for t in v.get("translations", []):
                    res_id = t.get("resource_id")
                    if res_id in TARGET_MAPPING:
                        info = TARGET_MAPPING[res_id]
                        cursor.execute(
                            """
                            INSERT INTO translations (verse_id, language_code, translation_text, translator_name)
                            VALUES (?, ?, ?, ?)
                        """,
                            (
                                v_id,
                                info["lang"],
                                t.get("text", ""),
                                info["translator_name"],
                            ),
                        )

                # Insert Words
                for w in v.get("words", []):
                    pos = w.get("position")
                    w_id = w.get("id")
                    if not w_id:
                        continue

                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO words (
                            id, verse_id, position, text_arabic,
                            trans_en, trans_ur, trans_id, audio_key
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            w_id,
                            v_id,
                            pos,
                            w.get("text_uthmani", w.get("text", "")),
                            w.get("translation", {}).get("text")
                            if w.get("translation")
                            else None,
                            ur_word_trans.get((v_key, pos)),
                            id_word_trans.get((v_key, pos)),
                            w.get("audio_url"),
                        ),
                    )

            conn.commit()
            print(f"  Finished chapter {ch_id}.")

    conn.close()
    print(f"Database population complete! File saved at: {DB_PATH}")


if __name__ == "__main__":
    populate_database()

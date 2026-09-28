"""
add_watchlist_person.py

Standalone script to add someone to person_missing or person_wanted.
Run this from inside the person/ folder (so its imports resolve),
with the venv activated.

Usage:
    python add_watchlist_person.py missing "Ramesh Kumar" /path/to/photo.jpg
    python add_watchlist_person.py wanted  "John Doe"      /path/to/photo.jpg
"""

import sys
import asyncio
import uuid

import cv2

from db import get_session, init_db
from matching.embed_reference import embed_reference_photo


async def add_person(category: str, name: str, photo_path: str):
    if category not in ("missing", "wanted"):
        print("category must be 'missing' or 'wanted'")
        return

    image = cv2.imread(photo_path)
    if image is None:
        print(f"Could not read image at {photo_path} -- check the path")
        return

    try:
        embedding = embed_reference_photo(image)
    except ValueError as e:
        print(f"Could not use that photo: {e}")
        return
    except RuntimeError as e:
        print(f"Model error: {e}")
        return

    embedding_literal = "[" + ",".join(str(x) for x in embedding) + "]"
    person_id = str(uuid.uuid4())

    from sqlalchemy import text

    table = "person_missing" if category == "missing" else "person_wanted"

    async with get_session() as session:
        if category == "missing":
            await session.execute(
                text(f"""
                    INSERT INTO {table} (person_id, name, reference_embedding, reference_image_path)
                    VALUES (:person_id, :name, CAST(:embedding AS VECTOR), :photo_path)
                """),
                {
                    "person_id": person_id,
                    "name": name,
                    "embedding": embedding_literal,
                    "photo_path": photo_path,
                },
            )
        else:
            await session.execute(
                text(f"""
                    INSERT INTO {table} (person_id, name, reference_embedding, reference_image_path)
                    VALUES (:person_id, :name, CAST(:embedding AS VECTOR), :photo_path)
                """),
                {
                    "person_id": person_id,
                    "name": name,
                    "embedding": embedding_literal,
                    "photo_path": photo_path,
                },
            )
        await session.commit()

    print(f"Added '{name}' to {table} with person_id={person_id}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python add_watchlist_person.py <missing|wanted> \"<name>\" <photo_path>")
        sys.exit(1)

    category_arg, name_arg, photo_path_arg = sys.argv[1], sys.argv[2], sys.argv[3]
    asyncio.run(add_person(category_arg, name_arg, photo_path_arg))
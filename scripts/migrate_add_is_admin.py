import sys
import os
# Add parent directory to path so we can import from kartoteka_web
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import create_engine, text
from kartoteka_web.database import DATABASE_URL

engine = create_engine(DATABASE_URL)

def migrate():
    print("Checking if 'is_admin' column exists in 'user' table...")
    with engine.connect() as connection:
        try:
            # Try to select the column
            connection.execute(text("SELECT is_admin FROM user LIMIT 1"))
            print("Column 'is_admin' already exists.")
        except Exception:
            print("Column 'is_admin' missing. Adding it...")
            try:
                # SQLite syntax to add column
                connection.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                connection.commit()
                print("Successfully added 'is_admin' column.")
            except Exception as e:
                print(f"Error adding column: {e}")

if __name__ == "__main__":
    migrate()

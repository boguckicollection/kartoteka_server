import sys
import os
# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import create_engine, text
from kartoteka_web.database import DATABASE_URL

engine = create_engine(DATABASE_URL)

def migrate():
    print("Checking for security columns in 'user' table...")
    with engine.connect() as connection:
        try:
            # Check if column exists
            connection.execute(text("SELECT failed_login_attempts FROM user LIMIT 1"))
            print("Security columns already exist.")
        except Exception:
            print("Security columns missing. Adding them...")
            try:
                # SQLite syntax to add columns
                connection.execute(text("ALTER TABLE user ADD COLUMN failed_login_attempts INTEGER DEFAULT 0"))
                connection.execute(text("ALTER TABLE user ADD COLUMN last_failed_login TIMESTAMP"))
                connection.execute(text("ALTER TABLE user ADD COLUMN locked_until TIMESTAMP"))
                connection.commit()
                print("Successfully added security columns.")
            except Exception as e:
                print(f"Error adding columns: {e}")

if __name__ == "__main__":
    migrate()

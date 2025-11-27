import sys
import os
# Add parent directory to path so we can import from kartoteka_web
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select, create_engine
from kartoteka_web.database import DATABASE_URL
from kartoteka_web.models import User
from kartoteka_web.auth import get_password_hash

engine = create_engine(DATABASE_URL)

def create_admin():
    print("Connecting to database...")
    
    # Get password from environment or use a default for local dev only
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        print("⚠️  No ADMIN_PASSWORD env var found. Using default dev password.")
        admin_password = "abrakadabra"
    
    with Session(engine) as session:
        # Check if user 'bogus' exists
        user = session.exec(select(User).where(User.username == "bogus")).first()
        
        if user:
            print("User 'bogus' already exists. Updating permissions...")
            user.is_admin = True
            # Optional: Update password if needed
            # user.hashed_password = get_password_hash(admin_password)
            session.add(user)
            session.commit()
            print("User 'bogus' promoted to admin.")
        else:
            print("Creating new admin user 'bogus'...")
            hashed_password = get_password_hash(admin_password)
            new_user = User(
                username="bogus",
                hashed_password=hashed_password,
                is_admin=True,
                email="admin@kartoteka.local"
            )
            session.add(new_user)
            session.commit()
            print("User 'bogus' created successfully with admin privileges.")

if __name__ == "__main__":
    create_admin()

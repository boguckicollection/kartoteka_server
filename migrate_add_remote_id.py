#!/usr/bin/env python
"""Migration script to add remote_id column to CardRecord and ProductRecord."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from kartoteka_web.database import engine

def migrate():
    """Add remote_id columns to CardRecord and ProductRecord tables."""
    
    print("=== Adding remote_id columns ===")
    
    with engine.begin() as conn:
        # Check if columns already exist
        result = conn.execute(text(
            "SELECT COUNT(*) FROM pragma_table_info('cardrecord') WHERE name='remote_id'"
        ))
        card_exists = result.scalar() > 0
        
        result = conn.execute(text(
            "SELECT COUNT(*) FROM pragma_table_info('productrecord') WHERE name='remote_id'"
        ))
        product_exists = result.scalar() > 0
        
        # Add remote_id to CardRecord if it doesn't exist
        if not card_exists:
            print("Adding remote_id to CardRecord...")
            conn.execute(text(
                "ALTER TABLE cardrecord ADD COLUMN remote_id VARCHAR"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_cardrecord_remote_id ON cardrecord (remote_id)"
            ))
            print("✓ Added remote_id to CardRecord")
        else:
            print("✓ remote_id already exists in CardRecord")
        
        # Add remote_id to ProductRecord if it doesn't exist
        if not product_exists:
            print("Adding remote_id to ProductRecord...")
            conn.execute(text(
                "ALTER TABLE productrecord ADD COLUMN remote_id VARCHAR"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_productrecord_remote_id ON productrecord (remote_id)"
            ))
            print("✓ Added remote_id to ProductRecord")
        else:
            print("✓ remote_id already exists in ProductRecord")
    
    print("\n=== Migration completed successfully! ===")
    print("\nNext steps:")
    print("1. Run: ./sync_catalog.py --verbose")
    print("   This will populate remote_id for existing cards")
    print("2. Restart server: uvicorn server:app --reload")
    print("3. Test history: curl 'http://localhost:8000/cards/stats?use_history=true'")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

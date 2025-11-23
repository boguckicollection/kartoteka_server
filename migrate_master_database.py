#!/usr/bin/env python
"""Migration script for Master Database implementation."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from kartoteka_web.database import engine

def migrate():
    """Add new tables and columns for Master Database functionality."""
    
    print("="*60)
    print("MIGRACJA: Master Database - Sukcesywna synchronizacja")
    print("="*60)
    
    with engine.begin() as conn:
        # ===== 1. CardRecord - dodaj pola sync =====
        print("\n[1/5] Aktualizacja CardRecord...")
        
        # Sprawdź które kolumny już istnieją
        result = conn.execute(text(
            "SELECT name FROM pragma_table_info('cardrecord')"
        ))
        existing_columns = {row[0] for row in result}
        
        columns_to_add = {
            'remote_id': 'VARCHAR',
            'sync_status': 'VARCHAR DEFAULT "pending"',
            'sync_priority': 'INTEGER DEFAULT 5',
            'last_synced': 'DATETIME',
            'sync_error': 'VARCHAR',
        }
        
        for col_name, col_type in columns_to_add.items():
            if col_name not in existing_columns:
                print(f"  Dodaję kolumnę: {col_name}")
                conn.execute(text(f"ALTER TABLE cardrecord ADD COLUMN {col_name} {col_type}"))
            else:
                print(f"  ✓ Kolumna {col_name} już istnieje")
        
        # Dodaj indeksy
        print("  Tworzę indeksy...")
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cardrecord_remote_id ON cardrecord (remote_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cardrecord_sync_status ON cardrecord (sync_status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cardrecord_sync_priority ON cardrecord (sync_priority)"))
        except Exception as e:
            print(f"  Ostrzeżenie przy tworzeniu indeksów: {e}")
        
        print("  ✓ CardRecord zaktualizowany")
        
        # ===== 2. ProductRecord - dodaj pola sync =====
        print("\n[2/5] Aktualizacja ProductRecord...")
        
        result = conn.execute(text(
            "SELECT name FROM pragma_table_info('productrecord')"
        ))
        existing_columns = {row[0] for row in result}
        
        for col_name, col_type in columns_to_add.items():
            if col_name not in existing_columns:
                print(f"  Dodaję kolumnę: {col_name}")
                conn.execute(text(f"ALTER TABLE productrecord ADD COLUMN {col_name} {col_type}"))
            else:
                print(f"  ✓ Kolumna {col_name} już istnieje")
        
        # Dodaj indeksy
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_productrecord_remote_id ON productrecord (remote_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_productrecord_sync_status ON productrecord (sync_status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_productrecord_sync_priority ON productrecord (sync_priority)"))
        except Exception as e:
            print(f"  Ostrzeżenie: {e}")
        
        print("  ✓ ProductRecord zaktualizowany")
        
        # ===== 3. Tabela PriceHistory =====
        print("\n[3/5] Tworzenie tabeli PriceHistory...")
        
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pricehistory'"
        ))
        if result.fetchone():
            print("  ✓ Tabela PriceHistory już istnieje")
        else:
            print("  Tworzę tabelę PriceHistory...")
            conn.execute(text("""
                CREATE TABLE pricehistory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_record_id INTEGER,
                    product_record_id INTEGER,
                    date DATE NOT NULL,
                    price REAL NOT NULL,
                    price_source VARCHAR NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (card_record_id) REFERENCES cardrecord(id),
                    FOREIGN KEY (product_record_id) REFERENCES productrecord(id),
                    UNIQUE (card_record_id, date, price_source)
                )
            """))
            
            # Indeksy
            conn.execute(text("CREATE INDEX ix_pricehistory_card_record_id ON pricehistory (card_record_id)"))
            conn.execute(text("CREATE INDEX ix_pricehistory_product_record_id ON pricehistory (product_record_id)"))
            conn.execute(text("CREATE INDEX ix_pricehistory_date ON pricehistory (date)"))
            conn.execute(text("CREATE INDEX ix_pricehistory_price_source ON pricehistory (price_source)"))
            
            print("  ✓ Tabela PriceHistory utworzona")
        
        # ===== 4. Tabela SetInfo =====
        print("\n[4/5] Tworzenie tabeli SetInfo...")
        
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='setinfo'"
        ))
        if result.fetchone():
            print("  ✓ Tabela SetInfo już istnieje")
        else:
            print("  Tworzę tabelę SetInfo...")
            conn.execute(text("""
                CREATE TABLE setinfo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code VARCHAR UNIQUE NOT NULL,
                    name VARCHAR NOT NULL,
                    series VARCHAR,
                    release_date DATE,
                    total_cards INTEGER,
                    synced_cards INTEGER DEFAULT 0,
                    sync_status VARCHAR DEFAULT 'pending',
                    sync_priority INTEGER DEFAULT 5,
                    last_synced DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """))
            
            # Indeksy
            conn.execute(text("CREATE INDEX ix_setinfo_code ON setinfo (code)"))
            conn.execute(text("CREATE INDEX ix_setinfo_sync_status ON setinfo (sync_status)"))
            conn.execute(text("CREATE INDEX ix_setinfo_sync_priority ON setinfo (sync_priority)"))
            
            print("  ✓ Tabela SetInfo utworzona")
        
        # ===== 5. Inicjalizuj SetInfo dla najnowszych setów =====
        print("\n[5/5] Inicjalizacja SetInfo dla setów Scarlet & Violet...")
        
        # Sprawdź czy już są jakieś wpisy
        result = conn.execute(text("SELECT COUNT(*) FROM setinfo"))
        count = result.scalar()
        
        if count == 0:
            print("  Dodaję najnowsze sety Pokemon TCG...")
            
            # Najnowsze sety (Scarlet & Violet) - priorytet 1
            sv_sets = [
                ('sv08', 'Surging Sparks', 'Scarlet & Violet', '2024-11-08', 1),
                ('sv07', 'Stellar Crown', 'Scarlet & Violet', '2024-09-13', 1),
                ('sv06', 'Twilight Masquerade', 'Scarlet & Violet', '2024-05-24', 1),
                ('sv05', 'Temporal Forces', 'Scarlet & Violet', '2024-03-22', 1),
                ('sv04', 'Paradox Rift', 'Scarlet & Violet', '2023-11-03', 1),
                ('sv03', 'Obsidian Flames', 'Scarlet & Violet', '2023-08-11', 1),
                ('sv02', 'Paldea Evolved', 'Scarlet & Violet', '2023-06-09', 1),
                ('sv01', 'Scarlet & Violet', 'Scarlet & Violet', '2023-03-31', 1),
            ]
            
            now = 'datetime("now")'
            for code, name, series, release, priority in sv_sets:
                conn.execute(text(f"""
                    INSERT INTO setinfo (code, name, series, release_date, sync_priority, sync_status, created_at, updated_at)
                    VALUES ('{code}', '{name}', '{series}', '{release}', {priority}, 'pending', {now}, {now})
                """))
                print(f"  ✓ Dodano: {code} - {name}")
        else:
            print(f"  ✓ SetInfo już zawiera {count} setów")
    
    print("\n" + "="*60)
    print("✅ MIGRACJA ZAKOŃCZONA POMYŚLNIE!")
    print("="*60)
    print("\n📋 Następne kroki:")
    print("1. Sprawdź bazę: sqlite3 kartoteka.sqlite '.schema'")
    print("2. Zweryfikuj tabele:")
    print("   SELECT * FROM setinfo;")
    print("   SELECT COUNT(*) FROM cardrecord WHERE sync_status='pending';")
    print("3. Uruchom server: uvicorn server:app --reload")
    print("4. Następny etap: Implementacja schedulera")
    print()

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\n❌ BŁĄD MIGRACJI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

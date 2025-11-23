#!/usr/bin/env python
"""Simple migration script using SQLite directly (no dependencies)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def migrate():
    """Add new tables and columns for Master Database functionality."""
    
    # Znajdź plik bazy danych
    db_path = Path(__file__).parent / "kartoteka.db"
    
    # Fallback do kartoteka.sqlite jeśli nie ma .db
    if not db_path.exists():
        db_path = Path(__file__).parent / "kartoteka.sqlite"
    
    if not db_path.exists():
        print(f"❌ Nie znaleziono bazy danych")
        print("   Sprawdzono: kartoteka.db i kartoteka.sqlite")
        print("   Uruchom najpierw serwer aby utworzyć bazę danych.")
        sys.exit(1)
    
    print("="*60)
    print("MIGRACJA: Master Database - Sukcesywna synchronizacja")
    print("="*60)
    print(f"Baza danych: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # ===== 1. CardRecord - dodaj pola sync =====
        print("\n[1/5] Aktualizacja CardRecord...")
        
        # Sprawdź które kolumny już istnieją
        cursor.execute("PRAGMA table_info(cardrecord)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        columns_to_add = [
            ('remote_id', 'VARCHAR'),
            ('sync_status', 'VARCHAR DEFAULT "pending"'),
            ('sync_priority', 'INTEGER DEFAULT 5'),
            ('last_synced', 'DATETIME'),
            ('sync_error', 'VARCHAR'),
        ]
        
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                print(f"  Dodaję kolumnę: {col_name}")
                cursor.execute(f"ALTER TABLE cardrecord ADD COLUMN {col_name} {col_type}")
            else:
                print(f"  ✓ Kolumna {col_name} już istnieje")
        
        # Dodaj indeksy
        print("  Tworzę indeksy...")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_cardrecord_remote_id ON cardrecord (remote_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_cardrecord_sync_status ON cardrecord (sync_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_cardrecord_sync_priority ON cardrecord (sync_priority)")
        
        print("  ✓ CardRecord zaktualizowany")
        
        # ===== 2. ProductRecord - dodaj pola sync =====
        print("\n[2/5] Aktualizacja ProductRecord...")
        
        cursor.execute("PRAGMA table_info(productrecord)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                print(f"  Dodaję kolumnę: {col_name}")
                cursor.execute(f"ALTER TABLE productrecord ADD COLUMN {col_name} {col_type}")
            else:
                print(f"  ✓ Kolumna {col_name} już istnieje")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_productrecord_remote_id ON productrecord (remote_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_productrecord_sync_status ON productrecord (sync_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_productrecord_sync_priority ON productrecord (sync_priority)")
        
        print("  ✓ ProductRecord zaktualizowany")
        
        # ===== 3. Tabela PriceHistory =====
        print("\n[3/5] Tworzenie tabeli PriceHistory...")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pricehistory'")
        if cursor.fetchone():
            print("  ✓ Tabela PriceHistory już istnieje")
        else:
            print("  Tworzę tabelę PriceHistory...")
            cursor.execute("""
                CREATE TABLE pricehistory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_record_id INTEGER,
                    product_record_id INTEGER,
                    date DATE NOT NULL,
                    price REAL NOT NULL,
                    price_source VARCHAR NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (card_record_id) REFERENCES cardrecord(id),
                    FOREIGN KEY (product_record_id) REFERENCES productrecord(id)
                )
            """)
            
            # Indeksy
            cursor.execute("CREATE INDEX ix_pricehistory_card_record_id ON pricehistory (card_record_id)")
            cursor.execute("CREATE INDEX ix_pricehistory_product_record_id ON pricehistory (product_record_id)")
            cursor.execute("CREATE INDEX ix_pricehistory_date ON pricehistory (date)")
            cursor.execute("CREATE INDEX ix_pricehistory_price_source ON pricehistory (price_source)")
            
            # Unique constraint
            cursor.execute("CREATE UNIQUE INDEX uq_price_history ON pricehistory (card_record_id, date, price_source)")
            
            print("  ✓ Tabela PriceHistory utworzona")
        
        # ===== 4. Tabela SetInfo =====
        print("\n[4/5] Tworzenie tabeli SetInfo...")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='setinfo'")
        if cursor.fetchone():
            print("  ✓ Tabela SetInfo już istnieje")
        else:
            print("  Tworzę tabelę SetInfo...")
            cursor.execute("""
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
            """)
            
            # Indeksy
            cursor.execute("CREATE INDEX ix_setinfo_code ON setinfo (code)")
            cursor.execute("CREATE INDEX ix_setinfo_sync_status ON setinfo (sync_status)")
            cursor.execute("CREATE INDEX ix_setinfo_sync_priority ON setinfo (sync_priority)")
            
            print("  ✓ Tabela SetInfo utworzona")
        
        # ===== 5. Inicjalizuj SetInfo dla najnowszych setów =====
        print("\n[5/5] Inicjalizacja SetInfo dla setów Scarlet & Violet...")
        
        cursor.execute("SELECT COUNT(*) FROM setinfo")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("  Dodaję najnowsze sety Pokemon TCG...")
            
            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            
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
            
            for code, name, series, release, priority in sv_sets:
                cursor.execute("""
                    INSERT INTO setinfo (code, name, series, release_date, sync_priority, sync_status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """, (code, name, series, release, priority, now, now))
                print(f"  ✓ Dodano: {code} - {name}")
        else:
            print(f"  ✓ SetInfo już zawiera {count} setów")
        
        # Commit wszystkich zmian
        conn.commit()
        
        print("\n" + "="*60)
        print("✅ MIGRACJA ZAKOŃCZONA POMYŚLNIE!")
        print("="*60)
        print("\n📋 Weryfikacja:")
        
        # Pokaż statystyki
        cursor.execute("SELECT COUNT(*) FROM setinfo")
        sets_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM cardrecord")
        cards_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM pricehistory")
        history_count = cursor.fetchone()[0]
        
        print(f"  Sety w bazie: {sets_count}")
        print(f"  Karty w bazie: {cards_count}")
        print(f"  Historia cen: {history_count} rekordów")
        
        print("\n📋 Następne kroki:")
        print("1. Uruchom server: uvicorn server:app --reload")
        print("2. Sprawdź czy działa: http://localhost:8000/collection")
        print("3. Gotowy na ETAP 2: Scheduler!")
        print()
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\n❌ BŁĄD MIGRACJI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python3
"""
Script to populate SetInfo table from tcg_sets.json and sync cards from API.

Usage:
    python scripts/populate_sets.py [--sync-cards] [--limit N] [--set CODE]
    
Options:
    --sync-cards    Also sync cards from RapidAPI for each set
    --limit N       Limit cards per set during sync (default: all)
    --set CODE      Sync only specific set code
    --dry-run       Show what would be done without making changes
"""

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env manually if exists
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

from sqlmodel import Session, select

from kartoteka_web import models
from kartoteka_web.database import engine
from kartoteka_web.services import catalog_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Era order for release dates estimation
ERA_ORDER = [
    ("Mega Evolution", "2025"),
    ("Scarlet & Violet", "2023"),
    ("Sword & Shield", "2020"),
    ("Sun & Moon", "2017"),
    ("XY", "2014"),
    ("Black & White", "2011"),
    ("HeartGold SoulSilver", "2010"),
    ("HeartGold & SoulSilver", "2010"),
    ("Platinum", "2009"),
    ("Diamond & Pearl", "2007"),
    ("EX Series", "2003"),
    ("EX", "2003"),
    ("E-Card", "2002"),
    ("e-Card", "2002"),
    ("Neo", "2000"),
    ("Gym", "1999"),
    ("Base Set", "1999"),
    ("Base", "1999"),
]


def get_era_year(era_name: str) -> str:
    """Get approximate release year for an era."""
    for era, year in ERA_ORDER:
        if era.lower() == era_name.lower():
            return year
    return "2020"  # Default


def load_sets_from_json(json_path: Path) -> list[dict]:
    """Load sets from tcg_sets.json file."""
    if not json_path.exists():
        logger.error(f"JSON file not found: {json_path}")
        return []
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON: {e}")
        return []
    
    sets = []
    for series_name, sets_list in data.items():
        if not isinstance(sets_list, list):
            continue
        
        year = get_era_year(series_name)
        for idx, set_info in enumerate(sets_list):
            if not isinstance(set_info, dict):
                continue
            
            code = set_info.get("code", "").strip()
            if not code:
                continue
            
            # Estimate release date based on era and position
            month = min(12, idx + 1)
            estimated_date = f"{year}-{month:02d}-01"
            
            sets.append({
                "code": code,
                "name": set_info.get("name", code),
                "series": series_name,
                "abbr": set_info.get("abbr", ""),
                "release_date": estimated_date,
            })
    
    return sets


def populate_set_info(session: Session, sets: list[dict], dry_run: bool = False) -> tuple[int, int]:
    """Populate SetInfo table with set data."""
    added = 0
    updated = 0
    
    for set_data in sets:
        code = set_data["code"]
        
        # Check if set exists
        existing = session.exec(
            select(models.SetInfo).where(models.SetInfo.code == code)
        ).first()
        
        release_date = None
        if set_data.get("release_date"):
            try:
                release_date = dt.date.fromisoformat(set_data["release_date"])
            except ValueError:
                pass
        
        if existing:
            # Update if needed
            changed = False
            if existing.name != set_data["name"]:
                existing.name = set_data["name"]
                changed = True
            if existing.series != set_data["series"]:
                existing.series = set_data["series"]
                changed = True
            if release_date and existing.release_date != release_date:
                existing.release_date = release_date
                changed = True
            
            if changed:
                existing.updated_at = dt.datetime.now(dt.timezone.utc)
                if not dry_run:
                    session.add(existing)
                updated += 1
                logger.info(f"  Updated: {code} - {set_data['name']}")
        else:
            # Create new
            set_info = models.SetInfo(
                code=code,
                name=set_data["name"],
                series=set_data["series"],
                release_date=release_date,
                total_cards=0,
                synced_cards=0,
                sync_status="pending",
                sync_priority=5,
            )
            if not dry_run:
                session.add(set_info)
            added += 1
            logger.info(f"  Added: {code} - {set_data['name']} ({set_data['series']})")
    
    if not dry_run:
        session.commit()
    
    return added, updated


def update_set_card_counts(session: Session) -> int:
    """Update total_cards count in SetInfo from CardRecord."""
    updated = 0
    
    # Get card counts per set from CardRecord
    from sqlalchemy import func
    
    stmt = (
        select(
            models.CardRecord.set_code,
            func.count(models.CardRecord.id).label("card_count")
        )
        .where(models.CardRecord.set_code.is_not(None))
        .group_by(models.CardRecord.set_code)
    )
    
    results = session.exec(stmt).all()
    
    for row in results:
        set_code = row[0]
        card_count = row[1]
        
        if not set_code:
            continue
        
        # Find SetInfo by code (case-insensitive)
        set_info = session.exec(
            select(models.SetInfo).where(
                func.lower(models.SetInfo.code) == set_code.lower()
            )
        ).first()
        
        if set_info and set_info.total_cards != card_count:
            set_info.total_cards = card_count
            set_info.synced_cards = card_count
            set_info.updated_at = dt.datetime.now(dt.timezone.utc)
            session.add(set_info)
            updated += 1
            logger.info(f"  Updated card count: {set_code} = {card_count} cards")
    
    session.commit()
    return updated


def sync_cards_for_set(
    session: Session,
    set_code: str,
    limit: int | None = None,
    rapidapi_key: str | None = None,
    rapidapi_host: str | None = None,
) -> tuple[int, int, int]:
    """Sync cards for a single set from RapidAPI."""
    try:
        added, updated, requests = catalog_sync.sync_set(
            session,
            set_code,
            rapidapi_key=rapidapi_key,
            rapidapi_host=rapidapi_host,
            limit=limit,
        )
        session.commit()
        return added, updated, requests
    except Exception as e:
        logger.error(f"Failed to sync set {set_code}: {e}")
        return 0, 0, 0


def main():
    parser = argparse.ArgumentParser(description="Populate SetInfo and sync cards")
    parser.add_argument("--sync-cards", action="store_true", help="Also sync cards from API")
    parser.add_argument("--limit", type=int, default=None, help="Limit cards per set")
    parser.add_argument("--set", type=str, default=None, help="Sync only specific set code")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()
    
    # Load environment
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    rapidapi_host = os.getenv("RAPIDAPI_HOST")
    
    if args.sync_cards and not rapidapi_key:
        logger.error("RAPIDAPI_KEY not set. Cannot sync cards.")
        sys.exit(1)
    
    # Use database engine from module
    
    # Path to tcg_sets.json
    json_path = Path(__file__).parent.parent / "tcg_sets.json"
    
    logger.info("=" * 60)
    logger.info("KARTOTEKA - Set Population & Sync Script")
    logger.info("=" * 60)
    
    with Session(engine) as session:
        # Step 1: Load and populate SetInfo
        logger.info("\n[1/3] Loading sets from tcg_sets.json...")
        sets = load_sets_from_json(json_path)
        logger.info(f"Found {len(sets)} sets in JSON file")
        
        if args.set:
            sets = [s for s in sets if s["code"].lower() == args.set.lower()]
            logger.info(f"Filtered to set: {args.set}")
        
        logger.info("\n[2/3] Populating SetInfo table...")
        added, updated = populate_set_info(session, sets, dry_run=args.dry_run)
        logger.info(f"SetInfo: {added} added, {updated} updated")
        
        # Step 2: Update card counts from existing CardRecord
        logger.info("\n[2b/3] Updating card counts from CardRecord...")
        count_updated = update_set_card_counts(session)
        logger.info(f"Updated card counts for {count_updated} sets")
        
        # Step 3: Sync cards from API if requested
        if args.sync_cards:
            logger.info("\n[3/3] Syncing cards from RapidAPI...")
            
            total_added = 0
            total_updated = 0
            total_requests = 0
            
            set_codes = [s["code"] for s in sets]
            
            for i, code in enumerate(set_codes, 1):
                logger.info(f"\n  [{i}/{len(set_codes)}] Syncing {code}...")
                
                if args.dry_run:
                    logger.info(f"    [DRY RUN] Would sync {code}")
                    continue
                
                added, updated, requests = sync_cards_for_set(
                    session,
                    code,
                    limit=args.limit,
                    rapidapi_key=rapidapi_key,
                    rapidapi_host=rapidapi_host,
                )
                
                total_added += added
                total_updated += updated
                total_requests += requests
                
                logger.info(f"    Added: {added}, Updated: {updated}, API calls: {requests}")
                
                # Update SetInfo
                set_info = session.exec(
                    select(models.SetInfo).where(models.SetInfo.code == code)
                ).first()
                
                if set_info:
                    # Recount cards for this set
                    from sqlalchemy import func
                    card_count = session.exec(
                        select(func.count(models.CardRecord.id)).where(
                            models.CardRecord.set_code == code
                        )
                    ).one()
                    
                    set_info.total_cards = card_count
                    set_info.synced_cards = card_count
                    set_info.sync_status = "complete" if card_count > 0 else "pending"
                    set_info.last_synced = dt.datetime.now(dt.timezone.utc)
                    session.add(set_info)
                    session.commit()
            
            logger.info(f"\n  Total: {total_added} added, {total_updated} updated, {total_requests} API calls")
        else:
            logger.info("\n[3/3] Skipping card sync (use --sync-cards to enable)")
    
    logger.info("\n" + "=" * 60)
    logger.info("Done!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

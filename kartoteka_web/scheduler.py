"""Background scheduler for automatic card synchronization."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, select

from . import models
from .database import session_scope
from .services import catalog_sync, tcg_api, crud

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    """Get or create the global scheduler instance."""
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler(
            daemon=True,
            job_defaults={
                'coalesce': True,  # Combine missed runs
                'max_instances': 1,  # Only one instance of each job at a time
                'misfire_grace_time': 3600,  # 1 hour grace period
            }
        )
    return scheduler


def start_scheduler():
    """Start the background scheduler and register all jobs."""
    sched = get_scheduler()
    
    if sched.running:
        logger.info("Scheduler already running")
        return
    
    logger.info("Starting background scheduler...")
    
    # ===== JOB 1: Sync cards batch (100 cards/hour) =====
    # Uruchamiany co godzinę
    sched.add_job(
        func=sync_cards_batch,
        trigger=IntervalTrigger(hours=1),
        id='sync_cards_batch',
        name='Sync Cards Batch (100/hour)',
        replace_existing=True,
    )
    logger.info("  ✓ Registered: sync_cards_batch (every 1 hour)")
    
    # ===== JOB 2: Sync price history (500 cards/day) =====
    # Uruchamiany codziennie o 3:00
    sched.add_job(
        func=sync_price_history_batch,
        trigger=CronTrigger(hour=3, minute=0),
        id='sync_price_history',
        name='Sync Price History (500/day)',
        replace_existing=True,
    )
    logger.info("  ✓ Registered: sync_price_history (daily at 3:00)")
    
    # ===== JOB 3: Check for new sets (weekly) =====
    # Uruchamiany w poniedziałki o 2:00
    sched.add_job(
        func=check_new_sets,
        trigger=CronTrigger(day_of_week='mon', hour=2, minute=0),
        id='check_new_sets',
        name='Check New Sets (weekly)',
        replace_existing=True,
    )
    logger.info("  ✓ Registered: check_new_sets (Mondays at 2:00)")
    
    # Start scheduler
    sched.start()
    logger.info("✅ Scheduler started successfully!")
    
    # Log next run times
    for job in sched.get_jobs():
        logger.info(f"  Next run: {job.name} at {job.next_run_time}")


def stop_scheduler():
    """Stop the background scheduler."""
    sched = get_scheduler()
    if sched.running:
        logger.info("Stopping scheduler...")
        sched.shutdown(wait=False)
        logger.info("✓ Scheduler stopped")


# ============================================================================
# JOB FUNCTIONS
# ============================================================================

def sync_cards_batch():
    """
    Sync batch of 100 cards from API to CardRecord.
    
    Priority:
    1. New sets (priority=1)
    2. Cards in user collections (priority=2)
    3. Old sets (priority=5)
    """
    logger.info("=" * 60)
    logger.info("JOB: Sync Cards Batch")
    logger.info("=" * 60)
    
    batch_size = 100
    
    try:
        with session_scope() as session:
            # Find next set to sync (lowest priority number = highest priority)
            stmt = (
                select(models.SetInfo)
                .where(models.SetInfo.sync_status.in_(['pending', 'partial']))
                .order_by(models.SetInfo.sync_priority, models.SetInfo.code)
                .limit(1)
            )
            set_info = session.exec(stmt).first()
            
            if not set_info:
                logger.info("✓ All sets synchronized!")
                logger.info("  Checking for cards needing refresh...")
                
                # Find cards that need price refresh (older than 24h)
                yesterday = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
                stmt = (
                    select(models.CardRecord)
                    .where(
                        (models.CardRecord.last_synced < yesterday) |
                        (models.CardRecord.last_synced.is_(None))
                    )
                    .order_by(models.CardRecord.sync_priority)
                    .limit(batch_size)
                )
                cards_to_refresh = session.exec(stmt).all()
                
                if cards_to_refresh:
                    logger.info(f"  Found {len(cards_to_refresh)} cards to refresh")
                    # TODO: Implement card refresh logic in ETAP 3
                else:
                    logger.info("  All cards are up to date!")
                
                return
            
            logger.info(f"Syncing set: {set_info.code} - {set_info.name}")
            logger.info(f"  Priority: {set_info.sync_priority}")
            logger.info(f"  Status: {set_info.sync_status}")
            logger.info(f"  Progress: {set_info.synced_cards}/{set_info.total_cards or '?'}")
            
            # Sync cards from this set
            added, updated, request_count = catalog_sync.sync_set(
                session=session,
                set_code=set_info.code,
                limit=batch_size,
            )
            
            # Update set progress
            set_info.synced_cards += added + updated
            set_info.last_synced = dt.datetime.now(dt.timezone.utc)
            
            # Check if set is complete
            if set_info.total_cards and set_info.synced_cards >= set_info.total_cards:
                set_info.sync_status = 'complete'
                logger.info(f"  ✅ Set {set_info.code} COMPLETE!")
            else:
                set_info.sync_status = 'partial'
            
            session.add(set_info)
            session.commit()
            
            logger.info(f"  ✓ Added: {added}, Updated: {updated}")
            logger.info(f"  ✓ API requests: {request_count}")
            logger.info(f"  ✓ New progress: {set_info.synced_cards}/{set_info.total_cards or '?'}")
    
    except Exception as e:
        logger.error(f"❌ Error in sync_cards_batch: {e}", exc_info=True)


def sync_price_history_batch():
    """
    Sync price history for 500 cards per day.
    
    Priority:
    1. Cards with remote_id that have not been synced recently.
    """
    logger.info("=" * 60)
    logger.info("JOB: Sync Price History Batch")
    logger.info("=" * 60)
    
    batch_size = 500
    
    try:
        with session_scope() as session:
            # Find cards that need price history update (older than 24h)
            yesterday = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
            stmt = (
                select(models.CardRecord)
                .where(models.CardRecord.remote_id.isnot(None))
                .where(
                    (models.CardRecord.last_price_synced < yesterday) |
                    (models.CardRecord.last_price_synced.is_(None))
                )
                .order_by(models.CardRecord.last_price_synced.asc().nullsfirst())
                .limit(batch_size)
            )
            cards_to_sync = session.exec(stmt).all()
            
            if not cards_to_sync:
                logger.info("✓ All card prices are up to date.")
                return
                
            logger.info(f"Found {len(cards_to_sync)} cards for price history sync.")
            
            for i, card in enumerate(cards_to_sync):
                logger.info(f"  ({i+1}/{len(cards_to_sync)}) Syncing card: {card.name} ({card.set_code})")
                
                if not card.remote_id:
                    continue

                try:
                    history_data = tcg_api.fetch_card_price_history(card.remote_id)
                    if not history_data:
                        logger.info("    - No price history found.")
                        # Update sync time even if no data, to avoid retrying constantly
                        card.last_price_synced = dt.datetime.now(dt.timezone.utc)
                        session.add(card)
                        session.commit()
                        continue

                    normalized_history = tcg_api.normalize_price_history(history_data)
                    
                    if normalized_history:
                        added, updated = crud.upsert_price_history(
                            session, card_record_id=card.id, price_history=normalized_history
                        )
                        logger.info(f"    - Added: {added}, Updated: {updated} price points.")
                    
                    card.last_price_synced = dt.datetime.now(dt.timezone.utc)
                    session.add(card)
                    session.commit()

                except Exception as e:
                    logger.error(f"    - Error syncing price history for card {card.id}: {e}", exc_info=True)
                    session.rollback()

    except Exception as e:
        logger.error(f"❌ Error in sync_price_history_batch: {e}", exc_info=True)


def check_new_sets():
    """
    Check for new Pokemon TCG sets released.
    Automatically adds them to SetInfo with high priority.
    """
    logger.info("=" * 60)
    logger.info("JOB: Check New Sets")
    logger.info("=" * 60)
    
    try:
        with session_scope() as session:
            # Get current sets from database
            stmt = select(models.SetInfo.code)
            existing_codes = {code for (code,) in session.exec(stmt).all()}
            
            logger.info(f"  Current sets in DB: {len(existing_codes)}")
            
            # TODO: Implement set discovery from API in ETAP 3
            # For now, just log
            logger.info("  ⚠️ Set discovery not implemented yet - will be in ETAP 3")
            
    except Exception as e:
        logger.error(f"❌ Error in check_new_sets: {e}", exc_info=True)


# ============================================================================
# MANUAL TRIGGERS (for testing and admin panel)
# ============================================================================

def trigger_sync_now():
    """Manually trigger card sync (for testing/admin)."""
    logger.info("Manual trigger: sync_cards_batch")
    sync_cards_batch()


def trigger_price_sync_now():
    """Manually trigger price history sync (for testing/admin)."""
    logger.info("Manual trigger: sync_price_history_batch")
    sync_price_history_batch()


def get_scheduler_status() -> dict:
    """Get current scheduler status for admin panel."""
    sched = get_scheduler()
    
    jobs = []
    for job in sched.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger),
        })
    
    return {
        'running': sched.running,
        'jobs': jobs,
    }

"""Unit tests for SQLModel database models."""

from __future__ import annotations

from sqlalchemy.orm import selectinload
from sqlmodel import select

from kartoteka_web import database, models


def test_user_card_relationships(app_environment):
    with database.session_scope() as session:
        user = models.User(username="dawn", hashed_password="hashed:password")
        card = models.Card(
            name="Piplup",
            number="007",
            set_name="Diamond & Pearl",
            rarity="Common",
        )
        entry = models.CollectionEntry(owner=user, card=card, quantity=4, is_holo=True)
        session.add(entry)

    with database.session_scope() as session:
        stored = session.exec(
            select(models.CollectionEntry)
            .options(
                selectinload(models.CollectionEntry.owner),
                selectinload(models.CollectionEntry.card),
            )
        ).first()

        assert stored is not None
        assert stored.owner is not None
        assert stored.card is not None
        assert stored.owner.username == "dawn"
        assert stored.card.name == "Piplup"
        assert stored.quantity == 4
        assert stored.is_holo is True


def test_card_record_persistence(app_environment):
    with database.session_scope() as session:
        record = models.CardRecord(
            name="Charizard",
            name_normalized="charizard",
            number="004",
            number_display="4/102",
            total="102",
            set_name="Base Set",
            set_name_normalized="base set",
            set_code="base",
            set_code_clean="base",
            rarity="Rare",
            artist="Mitsuhiro Arita",
        )
        session.add(record)

    with database.session_scope() as session:
        stored = session.exec(
            select(models.CardRecord).where(models.CardRecord.name == "Charizard")
        ).first()

        assert stored is not None
        assert stored.number_display == "4/102"
        assert stored.set_code == "base"
        assert stored.artist == "Mitsuhiro Arita"

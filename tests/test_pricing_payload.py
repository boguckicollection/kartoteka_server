from kartoteka import pricing


def test_build_card_payload_normalizes_nested_text_fields():
    raw = {
        "name": "Pikachu",
        "card_number": "25",
        "total_prints": "102",
        "episode": {
            "name": "Base Set",
            "series": {"id": 1, "name": "Scarlet & Violet", "slug": "scarlet-violet"},
            "releaseDate": {"label": "1999-01-09"},
        },
        "artist": {"id": 414, "name": "kodama", "slug": "kodama"},
        "images": {"small": "https://example.com/pikachu-small.png"},
    }

    payload = pricing._build_card_payload(raw)
    assert payload is not None
    assert payload["artist"] == "kodama"
    assert payload["series"] == "Scarlet & Violet"
    assert payload["release_date"] == "1999-01-09"

from pathlib import Path

path = Path("shared/db.py")
text = path.read_text(encoding="utf-8")
old = """def insert_market_item(item: MarketItem, config: Optional[Settings] = None) -> Dict[str, Any]:
    query = \"\"\"
        INSERT INTO markets (external_id, title, category, url, metadata, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, COALESCE(%s, NOW()), COALESCE(%s, NOW()))
        ON CONFLICT (external_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            category = EXCLUDED.category,
            url = EXCLUDED.url,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING *
    \"\"\"
    params = (
        item.id,
        item.title,
        item.category,
        item.url or None,
        _json_dumps(item.metadata or {}),
        utcnow(),
        utcnow(),
    )
    return fetch_one(query, params, config)
"""
new = """def insert_market_item(item: MarketItem, config: Optional[Settings] = None) -> Dict[str, Any]:
    query = \"\"\"
        INSERT INTO markets (external_id, title, category, url, created_at, updated_at)
        VALUES (%s, %s, %s, %s, COALESCE(%s, NOW()), COALESCE(%s, NOW()))
        ON CONFLICT (external_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            category = EXCLUDED.category,
            url = EXCLUDED.url,
            updated_at = NOW()
        RETURNING *
    \"\"\"
    params = (
        item.id,
        item.title,
        item.category,
        item.url or None,
        utcnow(),
        utcnow(),
    )
    return fetch_one(query, params, config)
"""
if old not in text:
    raise SystemExit("target block not found")
path.write_text(text.replace(old, new), encoding="utf-8")

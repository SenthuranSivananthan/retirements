from scripts.feed import ENDPOINT, normalize

ITEM = {
    "id": "a", "title": "Retirement: API keys end on 31 March 2027",
    "description": '<p>Move to <a href="https://learn.microsoft.com/azure/">Entra ID</a>.</p>',
    "products": ["Monitor"], "tags": ["Retirements"], "created": "2026-11-01T10:00:00Z",
    "modified": "2026-11-05T08:30:45.1234567Z",
    "availabilities": [{"ring": "Retirement", "year": 2027, "month": "March"}],
}


def catalog():
    return {"schemaVersion": 2, "source": ENDPOINT, "retrievedAt": "2026-11-10T00:00:00Z", "records": [normalize(ITEM)]}


def page(url=None):
    return {"@odata.count": 1, "value": [ITEM]}

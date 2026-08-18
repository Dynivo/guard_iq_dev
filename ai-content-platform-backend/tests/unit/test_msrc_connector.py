"""MSRC source keeps the monthly security summaries used by GuardIQ."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.connectors.msrc import MSRCConnector


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "value": [
                {
                    "ID": "2026-Jun",
                    "Alias": "2026-Jun",
                    "DocumentTitle": "June 2026 Security Updates",
                    "InitialReleaseDate": "2026-06-09T07:00:00Z",
                },
                {
                    "ID": "legacy",
                    "Alias": "legacy",
                    "DocumentTitle": "Mariner Release Notes",
                    "InitialReleaseDate": "2026-08-01T07:00:00Z",
                },
                {
                    "ID": "2026-Jul",
                    "Alias": "2026-Jul",
                    "DocumentTitle": "July 2026 Security Updates",
                    "InitialReleaseDate": "2026-07-14T07:00:00Z",
                },
            ]
        }


@pytest.mark.asyncio
async def test_msrc_filters_legacy_documents_and_sorts_newest_first() -> None:
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=_Response())

    with patch(
        "app.infrastructure.connectors.msrc.httpx.AsyncClient",
        return_value=client,
    ):
        articles = await MSRCConnector().fetch({"max_items": 10})

    assert [article.summary for article in articles] == [
        "July 2026 Security Updates",
        "June 2026 Security Updates",
    ]
    assert all("Mariner" not in article.title for article in articles)

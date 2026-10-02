from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.workers.consumer import send_webhook_with_retry


@pytest.mark.asyncio
async def test_webhook_succeeds_on_third_attempt():
    error = httpx.ConnectError("temporary failure")
    mocked = AsyncMock(side_effect=[error, error, None])
    with patch("app.workers.consumer.send_webhook", mocked), patch(
        "app.workers.consumer.asyncio.sleep", new=AsyncMock()
    ) as sleep:
        await send_webhook_with_retry("https://example.com/hook", {"ok": True})

    assert mocked.await_count == 3
    assert [call.args[0] for call in sleep.await_args_list] == [1, 2]


@pytest.mark.asyncio
async def test_webhook_raises_after_three_attempts():
    error = httpx.ConnectError("still down")
    mocked = AsyncMock(side_effect=error)
    with patch("app.workers.consumer.send_webhook", mocked), patch(
        "app.workers.consumer.asyncio.sleep", new=AsyncMock()
    ):
        with pytest.raises(httpx.ConnectError):
            await send_webhook_with_retry("https://example.com/hook", {"ok": True})

    assert mocked.await_count == 3

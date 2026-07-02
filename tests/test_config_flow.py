from __future__ import annotations

import pytest

from custom_components.fsm.config_flow import FSMConfigFlow


@pytest.mark.asyncio
async def test_config_flow_user_step_aborts_not_supported() -> None:
    flow = FSMConfigFlow()

    result = await flow.async_step_user()

    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"

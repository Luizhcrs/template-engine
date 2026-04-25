import pytest
from pathlib import Path
from unittest.mock import AsyncMock
from engine.preset_loader import load_preset
from engine.llm_mapper import map_content

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_map_content_returns_llm_output():
    preset = load_preset(FIXTURES / "sample_preset")
    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = {"codigo": "TST.001", "objetivo": "extraído"}

    result = await map_content(preset, "texto fonte qualquer", mock_llm)

    assert result == {"codigo": "TST.001", "objetivo": "extraído"}
    mock_llm.generate_structured.assert_called_once()


@pytest.mark.asyncio
async def test_map_content_includes_pattern_and_source_in_prompt():
    preset = load_preset(FIXTURES / "sample_preset")
    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = {}

    await map_content(preset, "a fonte textual", mock_llm)

    prompt_arg, schema_arg = mock_llm.generate_structured.call_args[0]
    assert "Padrão" in prompt_arg or "Padrao" in prompt_arg
    assert "a fonte textual" in prompt_arg
    assert schema_arg == preset.schema_json


@pytest.mark.asyncio
async def test_map_content_includes_gold_docs_as_few_shot():
    preset = load_preset(FIXTURES / "sample_preset")
    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = {}

    await map_content(preset, "fonte", mock_llm)

    prompt_arg, _ = mock_llm.generate_structured.call_args[0]
    assert "Exemplos" in prompt_arg
    # gold-01.docx has "DOC.001" in its text
    assert "DOC.001" in prompt_arg


@pytest.mark.asyncio
async def test_map_content_truncates_oversized_source():
    preset = load_preset(FIXTURES / "sample_preset")
    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = {}

    huge = "X" * 50_000
    await map_content(preset, huge, mock_llm)

    prompt_arg, _ = mock_llm.generate_structured.call_args[0]
    # Prompt should contain 12000 X's, not 50000
    assert prompt_arg.count("X") <= 12_000

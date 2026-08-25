import os
import sys
import tempfile
import types
import unittest
from unittest import mock

from spt_piles.ai_extraction import AIExtractionError, _parse_spt_tool_output as _parse_tool_output


class TestParseToolOutput(unittest.TestCase):
    def test_parses_valid_readings_sorted_by_depth(self):
        data = {
            "readings": [
                {"depth_m": 2.0, "n_spt": 8, "soil_key": "argila", "soil_description_original": "Argila mole"},
                {"depth_m": 1.0, "n_spt": 4, "soil_key": "argila", "soil_description_original": "Argila mole"},
            ],
            "water_table_found": True,
            "water_table_depth_m": 1.5,
            "borehole_id": "SP-01",
            "notes": "Ensaio conforme NBR 6484",
        }
        result = _parse_tool_output(data, "/tmp/laudo.pdf", "claude-sonnet-5")

        self.assertEqual([r.depth_m for r in result.readings], [1.0, 2.0])
        self.assertTrue(result.water_table_found)
        self.assertEqual(result.water_table_depth_m, 1.5)
        self.assertEqual(result.borehole_id, "SP-01")
        self.assertEqual(result.source_pdf_path, "/tmp/laudo.pdf")
        self.assertEqual(result.model_used, "claude-sonnet-5")

    def test_filters_out_invalid_soil_key(self):
        data = {
            "readings": [
                {"depth_m": 1.0, "n_spt": 4, "soil_key": "argila", "soil_description_original": "Argila"},
                {"depth_m": 2.0, "n_spt": 6, "soil_key": "rocha_inexistente", "soil_description_original": "Rocha"},
            ],
            "water_table_found": False,
        }
        result = _parse_tool_output(data, "x.pdf", "m")
        self.assertEqual(len(result.readings), 1)
        self.assertEqual(result.readings[0].soil_key, "argila")

    def test_filters_out_malformed_entries(self):
        data = {
            "readings": [
                {"depth_m": 1.0, "n_spt": 4, "soil_key": "argila", "soil_description_original": "Argila"},
                {"depth_m": "não é número", "n_spt": 4, "soil_key": "argila", "soil_description_original": "x"},
                {"n_spt": 4, "soil_key": "argila", "soil_description_original": "faltando depth_m"},
            ],
            "water_table_found": False,
        }
        result = _parse_tool_output(data, "x.pdf", "m")
        self.assertEqual(len(result.readings), 1)

    def test_no_valid_readings_raises(self):
        data = {"readings": [], "water_table_found": False}
        with self.assertRaises(AIExtractionError):
            _parse_tool_output(data, "x.pdf", "m")

    def test_missing_api_key_raises_friendly_error(self):
        import os

        from spt_piles.ai_extraction import extract_spt_report

        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("spt_piles.config.load_api_key", return_value=None):
                with self.assertRaises(AIExtractionError):
                    extract_spt_report("/nonexistent/file.pdf")


class _FakeToolBlock:
    def __init__(self, input_dict: dict) -> None:
        self.type = "tool_use"
        self.input = input_dict


class _FakeMessage:
    def __init__(self, tool_input: dict | None, stop_reason: str = "tool_use") -> None:
        self.content = [_FakeToolBlock(tool_input)] if tool_input is not None else []
        self.stop_reason = stop_reason


class _FakeStreamContext:
    def __init__(self, final_message: _FakeMessage, captured_calls: list) -> None:
        self._final_message = final_message
        self._captured_calls = captured_calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get_final_message(self) -> _FakeMessage:
        return self._final_message


def _install_fake_anthropic(final_message: _FakeMessage) -> list:
    """Instala um módulo `anthropic` falso em sys.modules simulando
    `Anthropic(api_key=...).messages.stream(...)` como gerenciador de
    contexto (é isso que `_call_pdf_tool` deve usar - client.messages.stream,
    não client.messages.create - para não esbarrar no limite do SDK de
    'streaming obrigatório para respostas longas'). Retorna a lista de
    kwargs capturados em cada chamada de `.stream(...)`."""

    captured_calls: list = []

    class _FakeMessagesResource:
        def stream(self, **kwargs):
            captured_calls.append(kwargs)
            return _FakeStreamContext(final_message, captured_calls)

        def create(self, **kwargs):  # pragma: no cover - não deveria ser chamado
            raise AssertionError("client.messages.create não deveria ser usado - use .stream()")

    class _FakeAnthropicClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.messages = _FakeMessagesResource()

    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = _FakeAnthropicClient
    sys.modules["anthropic"] = fake_module
    return captured_calls


class TestCallPdfToolStreaming(unittest.TestCase):
    def setUp(self):
        self._original_anthropic = sys.modules.get("anthropic")
        self._tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        self._tmp.write(b"%PDF-1.4 fake content")
        self._tmp.close()
        self._api_key_patch = mock.patch("spt_piles.config.resolve_api_key", return_value="fake-key")
        self._api_key_patch.start()

    def tearDown(self):
        self._api_key_patch.stop()
        os.unlink(self._tmp.name)
        if self._original_anthropic is not None:
            sys.modules["anthropic"] = self._original_anthropic
        else:
            sys.modules.pop("anthropic", None)

    def test_uses_streaming_call_and_returns_tool_input(self):
        from spt_piles.ai_extraction import _call_pdf_tool

        final_message = _FakeMessage({"items": []}, stop_reason="tool_use")
        captured_calls = _install_fake_anthropic(final_message)

        data, model_name = _call_pdf_tool(
            self._tmp.name, "system prompt", {"name": "my_tool", "input_schema": {}}, "instruction",
        )

        self.assertEqual(data, {"items": []})
        self.assertEqual(len(captured_calls), 1)
        self.assertEqual(captured_calls[0]["tool_choice"], {"type": "tool", "name": "my_tool"})

    def test_respects_custom_max_tokens(self):
        from spt_piles.ai_extraction import _call_pdf_tool

        final_message = _FakeMessage({"items": []}, stop_reason="tool_use")
        captured_calls = _install_fake_anthropic(final_message)

        _call_pdf_tool(
            self._tmp.name, "system prompt", {"name": "my_tool", "input_schema": {}}, "instruction",
            max_tokens=32000,
        )

        self.assertEqual(captured_calls[0]["max_tokens"], 32000)

    def test_truncated_response_raises_friendly_error(self):
        from spt_piles.ai_extraction import _call_pdf_tool

        final_message = _FakeMessage({"items": []}, stop_reason="max_tokens")
        _install_fake_anthropic(final_message)

        with self.assertRaises(AIExtractionError) as ctx:
            _call_pdf_tool(
                self._tmp.name, "system prompt", {"name": "my_tool", "input_schema": {}}, "instruction",
            )
        self.assertIn("Eberick", str(ctx.exception))

    def test_missing_tool_use_block_raises(self):
        from spt_piles.ai_extraction import _call_pdf_tool

        final_message = _FakeMessage(None, stop_reason="end_turn")
        _install_fake_anthropic(final_message)

        with self.assertRaises(AIExtractionError):
            _call_pdf_tool(
                self._tmp.name, "system prompt", {"name": "my_tool", "input_schema": {}}, "instruction",
            )


if __name__ == "__main__":
    unittest.main()

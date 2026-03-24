import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import anthropic

from pipeline.cc_agent import MAX_TURNS, CCAgent


FAKE_REPORT = {"overall": "PASS", "has_groundtruth": True}


def _make_out(root, state, year):
    out = os.path.join(root, state, year, "output")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "judge_report.json"), "w") as f:
        json.dump(FAKE_REPORT, f)


def _text_block(text: str) -> MagicMock:
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _tool_use_block(id: str, name: str, inp: dict) -> MagicMock:
    b = MagicMock()
    b.type = "tool_use"
    b.id = id
    b.name = name
    b.input = inp
    return b


def _response(stop_reason: str, blocks: list) -> MagicMock:
    r = MagicMock()
    r.stop_reason = stop_reason
    r.content = blocks
    return r


def _mock_client(responses: list) -> MagicMock:
    client = MagicMock()
    client.messages.create.side_effect = responses
    return client


# --- prompt tests (unchanged) ---


def test_prompt_includes_state_and_year():
    prompt = CCAgent()._build_prompt("ca", "2025", prior_clean_py=None)
    assert "ca" in prompt and "2025" in prompt


def test_prompt_includes_prior_clean_py():
    prompt = CCAgent()._build_prompt(
        "ga", "2025", prior_clean_py="# prior script"
    )
    assert "prior script" in prompt


def test_prompt_references_validate_and_json_schema():
    prompt = CCAgent()._build_prompt("ca", "2025", prior_clean_py=None)
    assert "validate.py" in prompt
    assert "judge_report.json" in prompt


# --- run() tests ---


def test_run_invokes_sdk_client():
    with tempfile.TemporaryDirectory() as d:
        _make_out(d, "ca", "2025")
        agent = CCAgent(states_root=d)
        resp = _response("end_turn", [_text_block("Done.")])
        with patch("pipeline.cc_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = _mock_client([resp])
            agent.run("ca", "2025")
        mock_cls.assert_called_once()


def test_run_returns_error_on_api_error():
    with tempfile.TemporaryDirectory() as d:
        agent = CCAgent(states_root=d)
        with patch("pipeline.cc_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = (
                anthropic.APIConnectionError(request=MagicMock())
            )
            result = agent.run("ca", "2025")
        assert result.error is not None


def test_run_finds_prior_year_clean_py():
    with tempfile.TemporaryDirectory() as d:
        prior_src = os.path.join(d, "ga", "2024", "src")
        os.makedirs(prior_src)
        with open(os.path.join(prior_src, "clean.py"), "w") as f:
            f.write("# 2024 clean script")
        _make_out(d, "ga", "2025")
        agent = CCAgent(states_root=d)
        resp = _response("end_turn", [_text_block("Done.")])
        captured: list[dict] = []

        def capture(**kwargs):
            captured.extend(kwargs["messages"])
            return resp

        with patch("pipeline.cc_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = capture
            agent.run("ga", "2025")

        assert "2024 clean script" in captured[0]["content"]


def test_run_tool_use_loop_executes_two_turns():
    with tempfile.TemporaryDirectory() as d:
        _make_out(d, "ca", "2025")
        agent = CCAgent(states_root=d)
        turn1 = _response(
            "tool_use",
            [
                _text_block("Let me read a file."),
                _tool_use_block("tu_1", "bash", {"command": "echo hi"}),
            ],
        )
        turn2 = _response("end_turn", [_text_block("All done.")])
        client = _mock_client([turn1, turn2])
        with patch("pipeline.cc_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = client
            agent.run("ca", "2025")
        assert client.messages.create.call_count == 2


def test_append_to_file_creates_and_appends():
    with tempfile.TemporaryDirectory() as d:
        _make_out(d, "ca", "2025")
        agent = CCAgent(states_root=d, repo_root=d)
        turn1 = _response(
            "tool_use",
            [
                _tool_use_block(
                    "tu_1",
                    "append_to_file",
                    {"path": "out.py", "content": "import os\n"},
                )
            ],
        )
        turn2 = _response(
            "tool_use",
            [
                _tool_use_block(
                    "tu_2",
                    "append_to_file",
                    {"path": "out.py", "content": "print('hi')\n"},
                )
            ],
        )
        turn3 = _response("end_turn", [_text_block("Done.")])
        with patch("pipeline.cc_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = _mock_client([turn1, turn2, turn3])
            agent.run("ca", "2025")
        with open(os.path.join(d, "out.py")) as f:
            content = f.read()
        assert content == "import os\nprint('hi')\n"


def test_edit_file_replaces_string():
    with tempfile.TemporaryDirectory() as d:
        _make_out(d, "ca", "2025")
        target = os.path.join(d, "script.py")
        with open(target, "w") as f:
            f.write("x = 1\ny = 2\n")
        agent = CCAgent(states_root=d, repo_root=d)
        turn1 = _response(
            "tool_use",
            [
                _tool_use_block(
                    "tu_1",
                    "edit_file",
                    {
                        "path": "script.py",
                        "old_string": "x = 1",
                        "new_string": "x = 99",
                    },
                )
            ],
        )
        turn2 = _response("end_turn", [_text_block("Done.")])
        with patch("pipeline.cc_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = _mock_client([turn1, turn2])
            agent.run("ca", "2025")
        with open(target) as f:
            content = f.read()
        assert content == "x = 99\ny = 2\n"


def test_edit_file_errors_when_string_not_found():
    with tempfile.TemporaryDirectory() as d:
        _make_out(d, "ca", "2025")
        target = os.path.join(d, "script.py")
        with open(target, "w") as f:
            f.write("x = 1\n")
        agent = CCAgent(states_root=d, repo_root=d)
        turn1 = _response(
            "tool_use",
            [
                _tool_use_block(
                    "tu_1",
                    "edit_file",
                    {
                        "path": "script.py",
                        "old_string": "z = 99",
                        "new_string": "z = 0",
                    },
                )
            ],
        )
        turn2 = _response("end_turn", [_text_block("Done.")])
        with patch("pipeline.cc_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = _mock_client([turn1, turn2])
            agent.run("ca", "2025")
        # File should be unchanged
        with open(target) as f:
            assert f.read() == "x = 1\n"


def test_run_max_turns_returns_gracefully():
    with tempfile.TemporaryDirectory() as d:
        _make_out(d, "ca", "2025")
        agent = CCAgent(states_root=d)
        infinite = _response(
            "tool_use",
            [_tool_use_block("tu_x", "bash", {"command": "echo hi"})],
        )
        with patch("pipeline.cc_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = _mock_client([infinite] * (MAX_TURNS + 1))
            result = agent.run("ca", "2025")
        assert result is not None

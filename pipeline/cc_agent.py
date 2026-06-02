from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime

import anthropic

from pipeline.clean_runner import CleanResult
from pipeline.judge_parser import load_judge_report


logger = logging.getLogger(__name__)

MAX_TURNS = 100
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16384

TOOLS: list[dict] = [
    {
        "name": "read_file",
        "description": (
            "Read the complete contents of a file. "
            "Path must be relative to the repository root."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to repo root.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write content to a file, creating parent directories "
            "as needed. Path must be relative to the repository root."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to repo root.",
                },
                "content": {
                    "type": "string",
                    "description": "The full content to write.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "append_to_file",
        "description": (
            "Append content to the end of a file, creating it if needed. "
            "Use this to build up clean.py section by section — imports "
            "first, then each logical block — so no single response needs "
            "to contain the full file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to repo root.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to append.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Replace an exact string in a file with new content. "
            "old_string must appear exactly once. Use this for targeted "
            "fixes without rewriting the whole file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to repo root.",
                },
                "old_string": {
                    "type": "string",
                    "description": (
                        "Exact string to replace "
                        "(must appear exactly once in the file)."
                    ),
                },
                "new_string": {
                    "type": "string",
                    "description": "Replacement string.",
                },
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "bash",
        "description": (
            "Run a bash command in the repository root. "
            "stdout and stderr are both returned. "
            "Commands are not interactive — do not use editors or pagers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 120).",
                },
            },
            "required": ["command"],
        },
    },
]


class CCAgent:
    def __init__(self, states_root: str = "states", repo_root: str = "."):
        self._states_root = states_root
        self._repo_root = repo_root

    def _agent_log_path(self, state: str, year: str) -> str:
        log_dir = "pipeline/logs"
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        return os.path.join(log_dir, f"cc-agent-{state}-{year}-{ts}.log")

    def _find_prior_clean_py(self, state: str, year: str) -> str | None:
        state_dir = os.path.join(self._states_root, state)
        if not os.path.isdir(state_dir):
            return None
        prior_years = sorted(
            y
            for y in os.listdir(state_dir)
            if os.path.isdir(os.path.join(state_dir, y)) and y < year
        )
        for prior_year in reversed(prior_years):
            path = os.path.join(state_dir, prior_year, "src", "clean.py")
            if os.path.exists(path):
                with open(path) as f:
                    return f.read()
        return None

    def _has_readme(self, state: str) -> bool:
        path = os.path.join(
            self._repo_root, "readmes", f"{state.upper()}_README.md"
        )
        return os.path.isfile(path)

    def _has_csv_groundtruth(self, state: str, year: str) -> bool:
        gt_dir = os.path.join(
            self._states_root, state, year, "data", "groundtruth"
        )
        return os.path.isdir(gt_dir) and any(
            f.endswith(".csv") for f in os.listdir(gt_dir)
        )

    def _build_prompt(
        self, state: str, year: str, prior_clean_py: str | None
    ) -> str:
        has_gt = self._has_csv_groundtruth(state, year)
        groundtruth_note = (
            f"CSV groundtruth files are available in "
            f"states/{state}/{year}/data/groundtruth/ — use them in "
            f"validate.py for row count and value comparison."
            if has_gt
            else (
                "No CSV groundtruth exists for this state. Use "
                "pipeline/data/groundtruth.md as your quality reference "
                "when writing validate.py."
            )
        )
        readme_note = (
            f"A state-specific README is at "
            f"readmes/{state.upper()}_README.md "
            f"— read it before writing clean.py for context on this "
            f"state's data format, column names, and known quirks.\n\n"
            if self._has_readme(state)
            else ""
        )
        base = (
            f"Read AGENT_INSTRUCTIONS.md and DATA_PREPROCESSING.md, "
            f"then immediately start writing code. "
            f"Process state {state}, year {year}.\n\n"
            f"{readme_note}"
            f"IMPORTANT — write code incrementally, do not over-explore:\n"
            f"- Use `bash` with `head -5` or `python3 -c` snippets to "
            f"sample file structure. Do NOT read full CSV/xlsx files.\n"
            f"- By turn 3 at the latest, start writing "
            f"states/{state}/{year}/src/clean.py. "
            f"Use `write_file` for the header/imports, then "
            f"`append_to_file` to add each logical section "
            f"(loading, cleaning, output). "
            f"Use `edit_file` for targeted fixes. "
            f"Never try to write the entire file in a single `write_file` "
            f"call — build it up in pieces.\n"
            f"- Run clean.py from states/{state}/{year}/ as cwd: "
            f"python src/clean.py --input-dir data/input --output-dir output\n"
            f"- Then write and run src/validate.py from the same cwd.\n"
            f"- validate.py must write output/judge_report.md (human) "
            f"AND output/judge_report.json "
            f'({{"overall": "PASS|WARN|FAIL", "has_groundtruth": true|false}}).\n'
            f"- If judge report is FAIL, use `edit_file` to fix the "
            f"specific issue and re-run. "
            f"Stop as soon as you have a PASS or WARN.\n\n"
            f"{groundtruth_note}"
        )
        if prior_clean_py:
            base += (
                f"\n\nPrior year's clean.py for reference "
                f"(adapt as needed — do not copy blindly):\n\n"
                f"```python\n{prior_clean_py}\n```"
            )
        return base

    def _dispatch_tool(
        self,
        block,
        lf,
        repo_root: str,
    ) -> tuple[str, bool]:
        """Execute a tool call. Returns (result_text, is_error)."""
        name = block.name
        inp = block.input

        if name == "read_file":
            path = os.path.join(repo_root, inp["path"])
            try:
                with open(path) as f:
                    content = f.read()
                lf.write(
                    f"[tool:read_file] {inp['path']} ({len(content)} chars)\n"
                )
                lf.flush()
                return content, False
            except OSError as e:
                lf.write(f"[tool:read_file ERROR] {e}\n")
                lf.flush()
                return f"Error reading {inp['path']}: {e}", True

        elif name == "write_file":
            path = os.path.join(repo_root, inp["path"])
            content = inp["content"]
            try:
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(path, "w") as f:
                    f.write(content)
                lf.write(
                    f"[tool:write_file] {inp['path']} ({len(content)} chars)\n"
                )
                lf.flush()
                return f"Wrote {len(content)} chars to {inp['path']}", False
            except OSError as e:
                lf.write(f"[tool:write_file ERROR] {e}\n")
                lf.flush()
                return f"Error writing {inp['path']}: {e}", True

        elif name == "append_to_file":
            path = os.path.join(repo_root, inp["path"])
            content = inp["content"]
            try:
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(path, "a") as f:
                    f.write(content)
                lf.write(
                    f"[tool:append_to_file] {inp['path']}"
                    f" (+{len(content)} chars)\n"
                )
                lf.flush()
                return (
                    f"Appended {len(content)} chars to {inp['path']}",
                    False,
                )
            except OSError as e:
                lf.write(f"[tool:append_to_file ERROR] {e}\n")
                lf.flush()
                return f"Error appending to {inp['path']}: {e}", True

        elif name == "edit_file":
            path = os.path.join(repo_root, inp["path"])
            old_string = inp["old_string"]
            new_string = inp["new_string"]
            try:
                with open(path) as f:
                    content = f.read()
                count = content.count(old_string)
                if count == 0:
                    msg = (
                        f"old_string not found in {inp['path']} "
                        f"— check spacing/indentation"
                    )
                    lf.write(f"[tool:edit_file ERROR] {msg}\n")
                    lf.flush()
                    return f"Error: {msg}", True
                if count > 1:
                    msg = (
                        f"old_string appears {count} times in {inp['path']}"
                        f" — make it more specific"
                    )
                    lf.write(f"[tool:edit_file ERROR] {msg}\n")
                    lf.flush()
                    return f"Error: {msg}", True
                new_content = content.replace(old_string, new_string, 1)
                with open(path, "w") as f:
                    f.write(new_content)
                lf.write(f"[tool:edit_file] {inp['path']}\n")
                lf.flush()
                return f"Edited {inp['path']}", False
            except OSError as e:
                lf.write(f"[tool:edit_file ERROR] {e}\n")
                lf.flush()
                return f"Error editing {inp['path']}: {e}", True

        elif name == "bash":
            cmd = inp["command"]
            timeout = inp.get("timeout", 120)
            lf.write(f"[tool:bash] $ {cmd}\n")
            lf.flush()
            try:
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                out = proc.stdout
                if proc.stderr:
                    out += f"\n[stderr]\n{proc.stderr}"
                if proc.returncode != 0:
                    out += f"\n[exit code: {proc.returncode}]"
                out = out or "(no output)"
                lf.write(f"[tool:bash] exit={proc.returncode}\n{out}\n")
                lf.flush()
                return out, proc.returncode != 0
            except subprocess.TimeoutExpired:
                msg = f"Command timed out after {timeout}s"
                lf.write(f"[tool:bash TIMEOUT] {msg}\n")
                lf.flush()
                return msg, True
            except Exception as e:
                lf.write(f"[tool:bash ERROR] {e}\n")
                lf.flush()
                return f"Error: {e}", True

        lf.write(f"[tool ERROR] unknown tool: {name}\n")
        lf.flush()
        return f"Unknown tool: {name}", True

    def run(self, state: str, year: str) -> CleanResult:
        prior = self._find_prior_clean_py(state, year)
        prompt = self._build_prompt(state, year, prior_clean_py=prior)
        log_path = self._agent_log_path(state, year)
        repo_root = os.path.abspath(self._repo_root)

        logger.info(
            "[%s/%s] invoking SDK tool-use loop (model=%s, → %s)",
            state,
            year,
            MODEL,
            log_path,
        )
        logger.debug("[%s/%s] prompt:\n%s", state, year, prompt)

        messages: list[dict] = [{"role": "user", "content": prompt}]
        client = anthropic.Anthropic()

        try:
            with open(log_path, "w", buffering=1) as lf:
                lf.write(f"=== PROMPT ===\n{prompt}\n\n=== TURNS ===\n")

                for turn in range(MAX_TURNS):
                    lf.write(f"\n--- turn {turn + 1} ---\n")
                    lf.flush()

                    response = client.messages.create(
                        model=MODEL,
                        max_tokens=MAX_TOKENS,
                        tools=TOOLS,
                        messages=messages,
                    )

                    for block in response.content:
                        if block.type == "text":
                            lf.write(f"[assistant] {block.text}\n")
                        elif block.type == "tool_use":
                            lf.write(
                                f"[assistant:tool_use] {block.name}"
                                f" input={str(block.input)[:200]}\n"
                            )
                        lf.flush()

                    messages.append(
                        {"role": "assistant", "content": response.content}
                    )

                    if response.stop_reason == "end_turn":
                        lf.write("\n=== AGENT FINISHED (end_turn) ===\n")
                        logger.info(
                            "[%s/%s] agent finished in %d turn(s)",
                            state,
                            year,
                            turn + 1,
                        )
                        break

                    if response.stop_reason != "tool_use":
                        lf.write(
                            f"\n=== UNEXPECTED stop_reason:"
                            f" {response.stop_reason} ===\n"
                        )
                        logger.warning(
                            "[%s/%s] unexpected stop_reason: %s",
                            state,
                            year,
                            response.stop_reason,
                        )
                        break

                    tool_results: list[dict] = []
                    for block in response.content:
                        if block.type != "tool_use":
                            continue
                        result_text, is_error = self._dispatch_tool(
                            block, lf, repo_root
                        )
                        lf.write(
                            f"[tool_result] id={block.id} error={is_error}\n"
                        )
                        lf.flush()
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_text,
                                "is_error": is_error,
                            }
                        )

                    messages.append({"role": "user", "content": tool_results})

                else:
                    lf.write(f"\n=== MAX_TURNS ({MAX_TURNS}) REACHED ===\n")
                    logger.warning(
                        "[%s/%s] agent hit MAX_TURNS=%d without finishing",
                        state,
                        year,
                        MAX_TURNS,
                    )

        except anthropic.APIConnectionError as e:
            logger.error("[%s/%s] API connection error: %s", state, year, e)
            return CleanResult(state=state, year=year, judge=None, error=str(e))
        except anthropic.APIStatusError as e:
            logger.error(
                "[%s/%s] API status %d: %s",
                state,
                year,
                e.status_code,
                e.message,
            )
            return CleanResult(
                state=state,
                year=year,
                judge=None,
                error=f"API error {e.status_code}: {e.message}",
            )
        except anthropic.APITimeoutError as e:
            logger.error("[%s/%s] API timeout: %s", state, year, e)
            return CleanResult(
                state=state,
                year=year,
                judge=None,
                error="API request timed out",
            )
        except Exception as e:
            logger.error("[%s/%s] unexpected error: %s", state, year, e)
            return CleanResult(state=state, year=year, judge=None, error=str(e))

        logger.info(
            "[%s/%s] tool-use loop done — full output in %s",
            state,
            year,
            log_path,
        )

        output_dir = os.path.join(self._states_root, state, year, "output")
        try:
            judge = load_judge_report(output_dir)
        except FileNotFoundError as e:
            logger.error("[%s/%s] %s", state, year, e)
            return CleanResult(state=state, year=year, judge=None, error=str(e))
        logger.info("[%s/%s] judge report: %s", state, year, judge.overall)
        return CleanResult(state=state, year=year, judge=judge)

from __future__ import annotations

import json
import queue
from typing import Any

import requests

import commands.config as config
from project_types import LightsLike
from audio import play_audio, text_to_speech
from commands.actions import sleep, throw_error
from commands.agent_tools import NATIVE_TOOL_DEFINITIONS, execute_native_tool
from commands.mcp_client import get_mcp_tools_groq_and_mapping, call_mcp_tool
from commands.cpu_mode.client import clean_content, query_groq
from commands.cpu_mode.detection import (
    looks_like_fake_tool_use,
    looks_like_limitation_or_suggestion,
    should_run_plan_round,
)
from commands.cpu_mode.prompts import (
    FAKE_TOOL_FOLLOWUP_PROMPT,
    LIMITATION_FOLLOWUP_PROMPT,
    PLAN_EXECUTE_PROMPT,
    PLAN_ONLY_PROMPT,
    SELF_EVAL_PROMPT,
    SYSTEM_MESSAGE,
)

_conversation_history: list[dict] = []


def _append_history(user_text: str, answer_text: str) -> None:
    _conversation_history.append({"role": "user", "content": user_text})
    _conversation_history.append({"role": "assistant", "content": clean_content(answer_text)})

    max_messages = 2 * (getattr(config, "CPU_MODE_HISTORY_TURNS", 5) or 0)
    if max_messages > 0 and len(_conversation_history) > max_messages:
        _conversation_history[:] = _conversation_history[-max_messages:]


def _build_messages(full_text: str) -> list[dict]:
    history_turns = getattr(config, "CPU_MODE_HISTORY_TURNS", 5) or 0
    history = _conversation_history[-(2 * history_turns) :] if history_turns else []
    return [
        {"role": "system", "content": SYSTEM_MESSAGE},
        *history,
        {"role": "user", "content": full_text},
    ]


def _execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    mcp_name_to_server: dict[str, Any],
    lights: LightsLike,
    q: queue.Queue[Any],
) -> bool:
    assistant_msg: dict[str, Any] = {"role": "assistant", "content": ""}
    assistant_msg["tool_calls"] = [
        {
            "id": tc["id"],
            "type": "function",
            "function": {
                "name": tc["function"]["name"],
                "arguments": tc["function"].get("arguments", "{}"),
            },
        }
        for tc in tool_calls
    ]
    messages.append(assistant_msg)

    exit_cpu_mode = False
    for tc in tool_calls:
        tid = tc["id"]
        fname = tc["function"]["name"]
        try:
            args_str = tc["function"].get("arguments") or "{}"
            args = json.loads(args_str) if isinstance(args_str, str) and args_str.strip() else args_str or {}
        except json.JSONDecodeError:
            args = {}

        content = None
        if fname in mcp_name_to_server:
            content = call_mcp_tool(mcp_name_to_server[fname], fname, args)
        if content is None:
            content, exit_cpu_mode = execute_native_tool(fname, args, lights, q)

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tid,
                "name": fname,
                "content": content,
            }
        )

    messages.append({"role": "user", "content": SELF_EVAL_PROMPT})
    return exit_cpu_mode


def handle_cpu_mode(
    full_text: str,
    q: queue.Queue[Any],
    lights: LightsLike,
) -> None:
    try:
        if "to sleep" in full_text:
            config.CPU_MODE = False
            play_audio("investigations_over")
            sleep(lights)
            return

        messages = _build_messages(full_text)
        mcp_tools, mcp_name_to_server = get_mcp_tools_groq_and_mapping()
        tools = mcp_tools + list(NATIVE_TOOL_DEFINITIONS)

        config.BUSY = True
        lights.set_color("thinking")
        plan_round_enabled = should_run_plan_round(full_text)
        plan_round_done = False

        try:
            iteration = 0
            while iteration < config.CPU_MODE_MAX_ITERATIONS:
                iteration += 1
                run_plan_round = plan_round_enabled and not plan_round_done and iteration == 1

                if run_plan_round:
                    plan_messages = [*messages, {"role": "user", "content": PLAN_ONLY_PROMPT}]
                    msg = query_groq(plan_messages, tools=None)
                else:
                    msg = query_groq(messages, tools if tools else None)

                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    exit_cpu_mode = _execute_tool_calls(tool_calls, messages, mcp_name_to_server, lights, q)
                    if exit_cpu_mode:
                        config.BUSY = False
                        with q.mutex:
                            q.queue.clear()
                        return
                    plan_round_done = True
                    continue

                answer_text = (msg.get("content") or "").strip()
                if not answer_text:
                    break

                if run_plan_round:
                    messages.append({"role": "assistant", "content": answer_text})
                    messages.append({"role": "user", "content": PLAN_EXECUTE_PROMPT})
                    plan_round_done = True
                    continue

                if iteration < config.CPU_MODE_MAX_ITERATIONS and looks_like_fake_tool_use(answer_text):
                    messages.append({"role": "assistant", "content": answer_text})
                    messages.append({"role": "user", "content": FAKE_TOOL_FOLLOWUP_PROMPT})
                    continue

                if iteration < config.CPU_MODE_MAX_ITERATIONS and looks_like_limitation_or_suggestion(answer_text):
                    messages.append({"role": "assistant", "content": answer_text})
                    messages.append({"role": "user", "content": LIMITATION_FOLLOWUP_PROMPT})
                    continue

                text_to_speech(answer_text)
                _append_history(full_text, answer_text)
                break
            else:
                for m in reversed(messages):
                    if m.get("role") == "assistant" and m.get("content"):
                        text_to_speech(m["content"].strip())
                        break
                else:
                    text_to_speech("I got nothing.")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                throw_error(lights, "You're out of free tokens, you little broke bitch")
            else:
                error_msg = f"API error: {e.response.status_code}"
                try:
                    error_detail = e.response.json().get("error", {}).get("message", "")
                    if error_detail:
                        error_msg = f"API error: {error_detail}"
                except Exception:
                    pass
                throw_error(lights, error_msg)
        except requests.exceptions.RequestException as e:
            throw_error(lights, f"Connection error: {str(e)}")

        lights.set_color("idle")
        config.BUSY = False
        with q.mutex:
            q.queue.clear()

    except Exception as e:
        config.BUSY = False
        throw_error(lights, e)

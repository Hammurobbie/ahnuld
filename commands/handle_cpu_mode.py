import json
import logging
import os
import re
import requests

import commands.config as config
from play_audio import play_audio
from text_to_speech import text_to_speech
from commands.actions import sleep, throw_error
from commands.agent_tools import NATIVE_TOOL_DEFINITIONS, execute_native_tool
from commands.mcp_client import get_mcp_tools_groq_and_mapping, call_mcp_tool

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_MESSAGE = f"""You are an AI assistant who speaks like Arnold Schwarzenegger's 90's sci-fi
characters. Be short, gruff, and in character. Dumb, funny one-liners are
encouraged, but be CONCISE and only use context when it's relevant to the
user's question. Never write function calls or tool syntax in your text responses.
Only use the provided tool calling mechanism.

CRITICAL TOOL RULES — you MUST follow these:
- To create a script: call the generate_script tool. NEVER say you created a
  script without actually calling generate_script.
- To run a script: call the execute_script tool. NEVER claim output from a
  script without actually calling execute_script.
- To list scripts: call the list_scripts tool. NEVER recite a script list from
  memory — always call list_scripts to get the real list.
- You CANNOT create, run, or list scripts through text alone. You MUST use the
  tool calls. If you skip the tool call, the action did not happen.
- Scripts may ONLY use the Python standard library (math, random, json, datetime,
  re, etc.). No yfinance, pandas, psutil, or other pip packages — use web_search
  for live or external data, then answer from the search results or write a script
  that uses only that data or pure math.
- When the user asks for things that need current or external data (stocks, news,
  prices, etc.), call web_search FIRST to get the data, then use that in your
  reply. Do not generate scripts that import third-party libraries.

IMPORTANT: Your responses are read aloud by a text-to-speech engine. You MUST
write everything as natural spoken language:
- NEVER use asterisks, markdown, hashtags, bullet points, or special symbols.
- Write out all units in full: say "degrees" not °F, "miles per hour" not mph,
  "inches" not in., "percent" not %.
- Write numbers as you would say them: "twenty eight degrees" or "28 degrees",
  not "28°F".
- No URLs, code blocks, or formatting of any kind.
- Keep responses to one or two short sentences.
- Never read code aloud, never quote source lines, and never spell out filenames
  character-by-character.
- For script workflows: briefly say the script was created and/or run, then
  summarize only the result.

When you call a tool and get a result, your next reply MUST include the key data
the user asked for (e.g. temperature and conditions for weather, the actual time
for time, specific facts from search). The user hears only your text, so say the
numbers and facts out loud, then add a one-liner if you want.

Do not repeat or regurgitate things you have already said in this conversation.
Reference earlier messages only when the user's current question directly asks
about or relates to something from the past. Otherwise answer the current
question freshly—do not echo or rephrase your previous replies.

Context: location: {os.environ.get('LOCATION_NAME', 'unknown')}"""

_conversation_history: list[dict] = []


def query_groq(messages, tools=None):
    """Call Groq chat completions. Returns the full message dict (content, tool_calls if any)."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }
    payload = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 550,
    }
    if tools is not None:
        payload["tools"] = tools
    resp = requests.post(GROQ_ENDPOINT, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    out = resp.json()
    return out["choices"][0]["message"]

def clean_content(text):
    """Remove malformed function call tags from assistant messages."""
    return re.sub(r'<function=.*?>', '', text or '').strip()


_FAKE_TOOL_RE = re.compile(
    r"script\s+(?:was\s+)?(?:created|saved|generated|written|initiated)"
    r"|(?:created|saved|generated|wrote)\s+\w+\.py"
    r"|(?:here(?:'s| is| are)\s+(?:the\s+)?(?:list|result|output).*\.py)"
    r"|(?:I (?:ran|executed|run|generate|created)\s+(?:a\s+)?(?:the\s+)?(?:script|\w+\.py))"
    r"|(?:generate\s+(?:a\s+)?script)"
    r"|prints?\s+(?:the\s+)?first\s+\w+\s+\w+\s+numbers",
    re.IGNORECASE,
)


def _looks_like_fake_tool_use(text: str) -> bool:
    return bool(_FAKE_TOOL_RE.search(text))


def handle_cpu_mode(full_text, q, lights):
    try:
        if "to sleep" in full_text:
            config.CPU_MODE = False
            play_audio("investigations_over")
            sleep(lights)
            return

        history_turns = getattr(config, "CPU_MODE_HISTORY_TURNS", 5) or 0
        history = _conversation_history[-(2 * history_turns) :] if history_turns else []
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            *history,
            {"role": "user", "content": full_text},
        ]

        mcp_tools, mcp_name_to_server = get_mcp_tools_groq_and_mapping()
        tools = mcp_tools + list(NATIVE_TOOL_DEFINITIONS)

        config.BUSY = True

        try:
            iteration = 0
            while iteration < config.CPU_MODE_MAX_ITERATIONS:
                iteration += 1
                msg = query_groq(messages, tools if tools else None)
                tool_calls = msg.get("tool_calls")

                if tool_calls:
                    assistant_msg = {"role": "assistant", "content": msg.get("content") or ""}
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
                        if exit_cpu_mode:
                            config.BUSY = False
                            with q.mutex:
                                q.queue.clear()
                            return
                    continue

                answer_text = (msg.get("content") or "").strip()

                if answer_text and iteration < config.CPU_MODE_MAX_ITERATIONS and _looks_like_fake_tool_use(answer_text):
                    messages.append({"role": "assistant", "content": answer_text})
                    messages.append({
                        "role": "user",
                        "content": (
                            "You did not actually call any tools. The action did not happen. "
                            "You MUST use the generate_script, execute_script, or list_scripts "
                            "tool call to perform script actions. Call the tool now."
                        ),
                    })
                    continue

                if answer_text:
                    text_to_speech(answer_text)
                    _conversation_history.append({"role": "user", "content": full_text})
                    _conversation_history.append({"role": "assistant", "content": clean_content(answer_text)})
                    max_messages = 2 * (getattr(config, "CPU_MODE_HISTORY_TURNS", 5) or 0)
                    if max_messages > 0 and len(_conversation_history) > max_messages:
                        _conversation_history[:] = _conversation_history[-max_messages:]
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
                error_msg = f"API error: {e.response_status_code}"
                try:
                    error_detail = e.response.json().get("error", {}).get("message", "")
                    if error_detail:
                        error_msg = f"API error: {error_detail}"
                except Exception:
                    pass
                throw_error(lights, error_msg)
        except requests.exceptions.RequestException as e:
            throw_error(lights, f"Connection error: {str(e)}")

        config.BUSY = False
        with q.mutex:
            q.queue.clear()

    except Exception as e:
        config.BUSY = False
        throw_error(lights, e)
        return

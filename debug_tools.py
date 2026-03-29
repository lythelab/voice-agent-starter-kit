"""Quick diagnostic: does llama-3.1-8b-instant actually call tools on Groq?"""
import asyncio
import json
import os
from dotenv import load_dotenv
import httpx

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    },
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        },
    }
]

MESSAGES = [
    {
        "role": "system",
        "content": (
            "You are a real-time voice assistant. You have access to tools — "
            "when a user asks for something a tool can handle (like weather), "
            "ALWAYS use the appropriate tool."
        ),
    },
    {"role": "user", "content": "Hey. Can you tell the weather today?"},
]


async def test_non_streaming():
    """Non-streaming call to see the raw response."""
    print(f"=== NON-STREAMING TEST (model={GROQ_MODEL}) ===")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": MESSAGES,
                "tools": TOOLS,
                "tool_choice": "auto",
                "temperature": 0.2,
                "max_tokens": 1024,
                "stream": False,
            },
            timeout=30,
        )
    data = resp.json()
    print(json.dumps(data, indent=2))

    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    finish_reason = choice.get("finish_reason")

    print(f"\n--- RESULT ---")
    print(f"finish_reason: {finish_reason}")
    print(f"content: {msg.get('content')}")
    print(f"tool_calls: {msg.get('tool_calls')}")

    if finish_reason == "tool_calls":
        print("\n✅ MODEL CALLED A TOOL!")
    elif msg.get("tool_calls"):
        print("\n✅ MODEL CALLED A TOOL (tool_calls present)!")
    else:
        print("\n❌ MODEL DID NOT CALL A TOOL — replied with text instead.")


async def test_streaming():
    """Streaming call to mirror what the adapter does."""
    print(f"\n=== STREAMING TEST (model={GROQ_MODEL}) ===")
    tool_calls_buffer = {}
    content_parts = []

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": MESSAGES,
                "tools": TOOLS,
                "tool_choice": "auto",
                "temperature": 0.2,
                "max_tokens": 1024,
                "stream": True,
            },
            timeout=30,
        ) as resp:
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                payload = json.loads(data)
                choices = payload.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                finish_reason = choices[0].get("finish_reason")

                if "tool_calls" in delta:
                    print(f"  [TOOL_CALL DELTA] {delta['tool_calls']}")
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.get("id", ""),
                                "function": {
                                    "name": tc.get("function", {}).get("name", ""),
                                    "arguments": "",
                                },
                            }
                        if tc.get("id"):
                            tool_calls_buffer[idx]["id"] = tc["id"]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            tool_calls_buffer[idx]["function"]["name"] = fn["name"]
                        if fn.get("arguments"):
                            tool_calls_buffer[idx]["function"]["arguments"] += fn["arguments"]
                else:
                    token = delta.get("content", "")
                    if token:
                        content_parts.append(token)

                if finish_reason:
                    print(f"  [FINISH] reason={finish_reason}")

    print(f"\n--- STREAMING RESULT ---")
    print(f"Content: {''.join(content_parts) or '(none)'}")
    print(f"Tool calls: {tool_calls_buffer or '(none)'}")
    if tool_calls_buffer:
        print("\n✅ STREAMING: Tool calls detected!")
    else:
        print("\n❌ STREAMING: No tool calls — model replied with text.")


asyncio.run(test_non_streaming())
asyncio.run(test_streaming())

"""
Test script to demonstrate the modular tool registry and filler words features.
"""

import asyncio
from app.pipeline.adapters import LLMAdapter, TTSAdapter
from app.pipeline.conversation import ConversationManager
from app.pipeline.tools import ToolRegistry, create_default_registry


async def test_tool_registry():
    """Test that the tool registry correctly registers and dispatches tools."""
    print("=== Testing Tool Registry ===")

    registry = create_default_registry()

    # Verify schemas are generated
    schemas = registry.get_schemas()
    print(f"Registered tools: {[s['function']['name'] for s in schemas]}")
    assert len(schemas) == 2, f"Expected 2 tools, got {len(schemas)}"

    # Execute weather tool directly
    result = await registry.execute("get_current_weather", {"location": "New York, NY", "unit": "fahrenheit"})
    print(f"Weather tool result: {result}")
    assert "New York" in result

    # Execute reminder tool directly
    result = await registry.execute("set_reminder", {"task": "call John", "time": "3:30 PM"})
    print(f"Reminder tool result: {result}")
    assert "call John" in result

    # Test unknown tool
    result = await registry.execute("nonexistent_tool", {})
    print(f"Unknown tool result: {result}")
    assert "Error" in result

    print("Tool registry test passed.\n")


async def test_custom_tool_registration():
    """Test adding a custom tool to the registry."""
    print("=== Testing Custom Tool Registration ===")

    registry = ToolRegistry()

    async def my_calculator(expression: str) -> str:
        """Evaluate a simple math expression."""
        try:
            result = eval(expression)  # noqa: S307 — demo only
            return f"The result of {expression} is {result}"
        except Exception as e:
            return f"Error: {e}"

    registry.register(
        name="calculator",
        description="Evaluate a math expression",
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression to evaluate"},
            },
            "required": ["expression"],
        },
        handler=my_calculator,
    )

    assert registry.has_tools()
    schemas = registry.get_schemas()
    print(f"Custom registry tools: {[s['function']['name'] for s in schemas]}")

    result = await registry.execute("calculator", {"expression": "2 + 3 * 4"})
    print(f"Calculator result: {result}")
    assert "14" in result

    print("Custom tool registration test passed.\n")


async def test_llm_with_registry():
    """Test that LLMAdapter accepts and uses a custom registry."""
    print("=== Testing LLM + Registry Integration ===")

    # Default registry
    llm_default = LLMAdapter()
    assert llm_default.tool_registry.has_tools()
    print(f"Default registry tools: {[s['function']['name'] for s in llm_default.tool_registry.get_schemas()]}")

    # Custom registry
    custom = ToolRegistry()

    async def echo(text: str) -> str:
        return f"Echo: {text}"

    custom.register(
        name="echo",
        description="Echo back text",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to echo"}},
            "required": ["text"],
        },
        handler=echo,
    )

    llm_custom = LLMAdapter(tool_registry=custom)
    schemas = llm_custom.tool_registry.get_schemas()
    print(f"Custom registry tools: {[s['function']['name'] for s in schemas]}")
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "echo"

    print("LLM + Registry integration test passed.\n")


async def test_streaming():
    """Test streaming tokens (requires GROQ_API_KEY or uses fallback)."""
    print("=== Testing Streaming Reply ===")

    llm = LLMAdapter()
    conversation = ConversationManager()

    query = "What's the weather like in New York?"
    conversation.add_user_message(query)

    print(f"User: {query}")
    print("Assistant: ", end="")

    tokens = []
    async for token in llm.stream_reply_tokens(conversation.get_messages()):
        tokens.append(token)
        print(token, end="")
    print()

    response = "".join(tokens).strip()
    assert len(response) > 0, "Expected non-empty response"
    print(f"\n(Total tokens: {len(tokens)}, Response length: {len(response)})")
    print("Streaming test passed.\n")


async def test_filler_words():
    """Test the filler words functionality."""
    print("=== Testing Filler Words ===")

    tts = TTSAdapter()

    # Temporarily increase the probability for testing
    original_prob = tts.filler_probability
    tts.filler_probability = 100  # 100% chance for testing

    test_sentences = [
        "Hello, how are you today?",
        "The weather is nice outside.",
        "I think we should go for a walk.",
        "Technology is advancing rapidly these days.",
    ]

    for sentence in test_sentences:
        # synthesize_with_fillers modifies text then calls synthesize,
        # which returns None without Cartesia keys — that's expected.
        result = await tts.synthesize_with_fillers(sentence)
        print(f"Original: {sentence}")
        print(f"TTS result: {result}  (None is expected without Cartesia API key)")
        print()

    # Restore original probability
    tts.filler_probability = original_prob

    print("Filler words test completed.\n")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("  Voice Agent Feature Tests")
    print("=" * 60 + "\n")

    await test_tool_registry()
    await test_custom_tool_registration()
    await test_llm_with_registry()
    await test_streaming()
    await test_filler_words()

    print("=" * 60)
    print("  All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
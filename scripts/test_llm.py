"""LLM connectivity and tool calling validation script.

Usage:
    python scripts/test_llm.py

Requires LLM_API_KEY in .env or environment.
"""

import sys
from datetime import datetime

from langchain_core.tools import tool

from src.config import Settings
from src.llm.adapter import get_chat_model


@tool
def get_current_date() -> str:
    """Return the current date in ISO format."""
    return datetime.now().strftime("%Y-%m-%d")


def test_simple_call(model):
    """Test a simple LLM call without tools."""
    print("=" * 60)
    print("Test 1: Simple LLM call")
    print("=" * 60)
    response = model.invoke("Olá, responda em uma frase curta em português: o que é SRAG?")
    print(f"Response: {response.content}\n")
    return response


def test_tool_calling(model):
    """Test LLM tool calling capability."""
    print("=" * 60)
    print("Test 2: Tool calling")
    print("=" * 60)
    model_with_tools = model.bind_tools([get_current_date])
    response = model_with_tools.invoke("Qual é a data de hoje?")

    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"Tool calls detected: {response.tool_calls}")
        for tc in response.tool_calls:
            if tc["name"] == "get_current_date":
                result = get_current_date.invoke({})
                print(f"Tool result: {result}")
                final_response = model_with_tools.invoke(
                    f"A data de hoje é {result}. Responda ao usuário."
                )
                print(f"Final response: {final_response.content}\n")
                return response
    else:
        print(f"No tool calls in response. Raw: {response}\n")
        print("WARNING: Tool calling may not be supported by this provider/model.")
        return response


def main():
    print("LLM Connectivity Validation")
    print("=" * 60)

    settings = Settings()
    print(f"Provider: {settings.llm_provider}")
    print(f"Model:    {settings.llm_model}")
    print()

    try:
        model = get_chat_model(settings)
        print(f"Model instantiated: {type(model).__name__}\n")
    except Exception as e:
        print(f"ERROR: Failed to instantiate model: {e}")
        print("\nTroubleshooting:")
        print("  - Check LLM_API_KEY in .env")
        print("  - Check LLM_PROVIDER and LLM_MODEL values")
        print("  - For OpenRouter/Groq: verify LLM_BASE_URL")
        sys.exit(1)

    results = {}

    try:
        results["simple_call"] = test_simple_call(model)
    except Exception as e:
        print(f"ERROR in simple call: {e}")
        results["simple_call_error"] = str(e)

    try:
        results["tool_calling"] = test_tool_calling(model)
    except Exception as e:
        print(f"ERROR in tool calling: {e}")
        results["tool_calling_error"] = str(e)

    print("=" * 60)
    print("Validation Summary")
    print("=" * 60)
    simple_ok = "simple_call" in results and "simple_call_error" not in results
    tool_ok = "tool_calling" in results and "tool_calling_error" not in results
    print(f"  Simple call:   {'OK' if simple_ok else 'FAILED'}")
    print(f"  Tool calling:  {'OK' if tool_ok else 'FAILED'}")

    if not tool_ok and settings.llm_provider == "gemini":
        print("\nIf tool calling failed, try switching provider:")
        print("  Set LLM_PROVIDER=openrouter in .env")
        print("  Set LLM_API_KEY=<your-openrouter-key> in .env")

    return 0 if (simple_ok and tool_ok) else 1


if __name__ == "__main__":
    sys.exit(main())

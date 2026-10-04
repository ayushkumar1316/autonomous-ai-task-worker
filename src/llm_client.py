"""LLM client - supports Groq and OpenRouter via OpenAI-compatible API."""
import json
import os
import time
import urllib.request

# Provider configs
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "allam-2-7b"],
        "default_model": "openai/gpt-oss-20b",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["meta-llama/llama-3.3-70b-instruct:free", "google/gemma-2-9b-it:free"],
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
    },
}


def call_llm(
    prompt: str,
    system: str = "",
    provider: str = "groq",
    api_key: str = "",
    model: str = "",
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict:
    """Call LLM API and return response dict.
    
    Returns: {"success": bool, "content": str, "error": str, "provider": str, "model": str, "latency_ms": int}
    """
    # Load API key from argument or env
    if not api_key:
        if provider == "groq":
            api_key = os.environ.get("GROQ_API_KEY", "")
        else:
            api_key = os.environ.get("OPENROUTER_API_KEY", "")

    if not api_key:
        return {
            "success": False,
            "content": "",
            "error": f"No API key provided for {provider}. Set {provider.upper()}_API_KEY env var or pass api_key parameter.",
            "provider": provider,
            "model": "",
            "latency_ms": 0,
        }

    # Select model
    if not model:
        model = PROVIDERS[provider]["default_model"]

    # Prepare request
    base_url = os.environ.get(f"{provider.upper()}_BASE_URL") or PROVIDERS[provider]["base_url"]
    url = f"{base_url}/chat/completions"

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        # Groq's edge (Cloudflare) rejects default urllib clients (error 1010)
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    # OpenRouter requires additional headers
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/ayushkumar1316/autonomous-ai-task-worker"
        headers["X-Title"] = "Autonomous AI Task Worker"

    # Make request
    start_time = time.time()
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.status
            response_body = response.read().decode("utf-8")
            latency_ms = int((time.time() - start_time) * 1000)

            if status_code == 200:
                result = json.loads(response_body)
                message = result["choices"][0]["message"]
                # Some models (gpt-oss) put actual response in "reasoning" field
                content = message.get("content", "")
                reasoning = message.get("reasoning", "")
                # For reasoning models, use reasoning if content is empty
                if not content and reasoning:
                    content = reasoning
                return {
                    "success": True,
                    "content": content,
                    "error": "",
                    "provider": provider,
                    "model": model,
                    "latency_ms": latency_ms,
                }
            else:
                return {
                    "success": False,
                    "content": "",
                    "error": f"HTTP {status_code}: {response_body}",
                    "provider": provider,
                    "model": model,
                    "latency_ms": latency_ms,
                }

    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error_body = e.read().decode("utf-8") if e.fp else ""
        return {
            "success": False,
            "content": "",
            "error": f"HTTP {e.code}: {error_body}",
            "provider": provider,
            "model": model,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "content": "",
            "error": str(e),
            "provider": provider,
            "model": model,
            "latency_ms": latency_ms,
        }


def test_connection(provider: str, api_key: str) -> dict:
    """Test LLM API connection."""
    result = call_llm(
        prompt="Say hello in 5 words.",
        system="You are a test.",
        provider=provider,
        api_key=api_key,
        max_tokens=50,
    )
    return result


if __name__ == "__main__":
    # Test both providers
    import sys

    groq_key = os.environ.get("GROQ_API_KEY", "")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")

    print("Testing Groq...")
    if groq_key:
        result = test_connection("groq", groq_key)
        print(f"  Success: {result['success']}, Model: {result['model']}, Latency: {result['latency_ms']}ms")
        if not result['success']:
            print(f"  Error: {result['error']}")
    else:
        print("  GROQ_API_KEY not set")

    print("\nTesting OpenRouter...")
    if openrouter_key:
        result = test_connection("openrouter", openrouter_key)
        print(f"  Success: {result['success']}, Model: {result['model']}, Latency: {result['latency_ms']}ms")
        if not result['success']:
            print(f"  Error: {result['error']}")
    else:
        print("  OPENROUTER_API_KEY not set")

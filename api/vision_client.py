"""
vision_client.py — Calls Ollama Vision API to extract content from slide/page images.

Uses qwen2.5vl:7b (or a configured model) running on the local machine (RTX 3060).
The Vision API endpoint is POST /api/chat with base64-encoded image in the message.
"""
import base64
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Default extraction prompt based on prompts_explore_pptx.md — G1 Full Content Dump
_DEFAULT_EXTRACTION_PROMPT = """\
You are extracting content from a technical training slide or document page.

Extract and report ALL of the following that are present:

TEXT:
- Title (exact words)
- All bullet points or body text (exact words, preserve hierarchy)
- Any labels, captions, or annotations
- Any numbers, versions, or code snippets visible

VISUALS:
- Describe each diagram, chart, or illustration in detail
- For flowcharts: list all nodes and the connections between them
- For tables: reproduce the structure in markdown table format
- For screenshots or UI images: describe what interface or output is shown

LAYOUT CLUES:
- Are text and visuals presented as separate sections, or are they interleaved?
- Does the visual appear to explain the text, or is it supplementary?

Rule: If something is not visible in the slide/page, do not include it.
Output everything in structured markdown format.
"""


def extract_image_content(
    image_bytes: bytes,
    model: Optional[str] = None,
    prompt: Optional[str] = None,
    host: Optional[str] = None,
    timeout: int = 60,
) -> str:
    """
    Call the Ollama Vision API to extract text and structure from an image.

    Args:
        image_bytes: Raw image bytes (PNG or JPEG)
        model: Ollama vision model name. Defaults to VISION_LLM_MODEL env var or 'qwen2.5vl:7b'
        prompt: Custom extraction prompt. Defaults to the G1 full content dump prompt.
        host: Ollama host URL. Defaults to OLLAMA_HOST env var or 'http://localhost:11434'
        timeout: Request timeout in seconds (default 60 — vision calls can be slow)

    Returns:
        str: Extracted content as markdown text. Empty string on failure.
    """
    if model is None:
        model = os.getenv("VISION_LLM_MODEL", "qwen2.5vl:7b")

    if prompt is None:
        prompt = _DEFAULT_EXTRACTION_PROMPT

    if host is None:
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        # Strip trailing slash
        host = host.rstrip("/")

    # Encode image to base64
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,  # Low temperature for factual extraction
        },
    }

    api_url = f"{host}/api/chat"
    logger.debug(f"Calling Ollama Vision API at {api_url} with model={model}")

    try:
        response = requests.post(api_url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        # Extract content from the response
        message = data.get("message", {})
        content = message.get("content", "")

        if content:
            logger.debug(f"Vision extraction returned {len(content)} chars")
            return content.strip()
        else:
            logger.warning(f"Vision API returned empty content for model={model}")
            return ""

    except requests.exceptions.Timeout:
        logger.error(f"Vision API request timed out after {timeout}s (model={model}, host={host})")
        return ""
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot connect to Ollama Vision API at {host}: {e}")
        return ""
    except requests.exceptions.HTTPError as e:
        logger.error(f"Ollama Vision API HTTP error: {e}, response: {response.text[:500]}")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error calling Vision API: {e}")
        return ""

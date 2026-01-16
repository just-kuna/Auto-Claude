"""
Simple iFlow SDK Client Factory
================================

Factory for creating minimal iFlow SDK clients for single-turn utility operations
like commit message generation, merge conflict resolution, and batch analysis.

These clients don't need full security configurations, MCP servers, or hooks.
Use `create_client()` from `core.client` for full agent sessions with security.

Example usage:
    from core.simple_client import create_simple_client

    # For commit message generation (text-only, no tools)
    client = create_simple_client(agent_type="commit_message")

    # For merge conflict resolution (text-only, no tools)
    client = create_simple_client(agent_type="merge_resolver")

    # For insights extraction (read tools only)
    client = create_simple_client(agent_type="insights", cwd=project_dir)
"""

import os
from pathlib import Path
from typing import Any

from agents.tools_pkg import get_agent_config, get_default_thinking_level
from core.auth import get_sdk_env_vars, require_auth_token, ensure_iflow_api_key
from core.iflow_client import (
    SyncIFlowClient,
    IFlowClientWrapper,
    find_iflow_cli,
    is_iflow_sdk_available,
    simple_query_sync,
)
from phase_config import get_thinking_budget


# Default model for simple operations (fast and efficient)
DEFAULT_SIMPLE_MODEL = "Qwen3-Coder"


def create_simple_client(
    agent_type: str = "merge_resolver",
    model: str = DEFAULT_SIMPLE_MODEL,
    system_prompt: str | None = None,
    cwd: Path | None = None,
    max_turns: int = 1,
    max_thinking_tokens: int | None = None,
) -> SyncIFlowClient:
    """
    Create a minimal iFlow SDK client for single-turn utility operations.

    This factory creates lightweight clients without MCP servers, security hooks,
    or full permission configurations. Use for text-only analysis tasks.

    Args:
        agent_type: Agent type from AGENT_CONFIGS. Determines available tools.
                   Common utility types:
                   - "merge_resolver" - Text-only merge conflict analysis
                   - "commit_message" - Text-only commit message generation
                   - "insights" - Read-only code insight extraction
                   - "batch_analysis" - Read-only batch issue analysis
                   - "batch_validation" - Read-only validation
        model: iFlow model to use (defaults to Qwen3-Coder for fast operations)
        system_prompt: Optional custom system prompt (for specialized tasks)
        cwd: Working directory for file operations (optional)
        max_turns: Maximum conversation turns (default: 1 for single-turn)
        max_thinking_tokens: Override thinking budget (None = use agent default from
                            AGENT_CONFIGS, converted using phase_config.THINKING_BUDGET_MAP)

    Returns:
        Configured SyncIFlowClient for single-turn operations

    Raises:
        ValueError: If agent_type is not found in AGENT_CONFIGS
        RuntimeError: If iFlow SDK is not available
    """
    # Ensure API key is available
    ensure_iflow_api_key()
    api_key = require_auth_token()

    # Get environment variables for SDK
    sdk_env = get_sdk_env_vars()

    # Get agent configuration (raises ValueError if unknown type)
    config = get_agent_config(agent_type)

    # Get tools from config (no MCP tools for simple clients)
    allowed_tools = list(config.get("tools", []))

    # Determine thinking budget using the single source of truth (phase_config.py)
    if max_thinking_tokens is None:
        thinking_level = get_default_thinking_level(agent_type)
        max_thinking_tokens = get_thinking_budget(thinking_level)

    # Find iFlow CLI path (handles non-standard installations)
    cli_path = find_iflow_cli()

    # Create synchronous client
    return SyncIFlowClient(
        api_key=api_key,
        model=model,
        working_directory=str(cwd.resolve()) if cwd else None,
        approval_mode="yolo",  # Simple clients use YOLO mode for efficiency
    )


async def create_simple_client_async(
    agent_type: str = "merge_resolver",
    model: str = DEFAULT_SIMPLE_MODEL,
    system_prompt: str | None = None,
    cwd: Path | None = None,
    max_turns: int = 1,
    max_thinking_tokens: int | None = None,
) -> IFlowClientWrapper:
    """
    Create a minimal async iFlow SDK client for single-turn utility operations.

    Same as create_simple_client but returns an async client.

    Args:
        Same as create_simple_client

    Returns:
        Configured IFlowClientWrapper for async single-turn operations
    """
    # Ensure API key is available
    ensure_iflow_api_key()
    api_key = require_auth_token()

    # Get agent configuration (raises ValueError if unknown type)
    config = get_agent_config(agent_type)

    # Create async client
    return IFlowClientWrapper(
        api_key=api_key,
        model=model,
        working_directory=str(cwd.resolve()) if cwd else None,
        approval_mode="yolo",
    )


def simple_query(prompt: str, model: str = DEFAULT_SIMPLE_MODEL) -> str:
    """
    Simple synchronous query for one-off AI requests.

    This is the simplest way to get an AI response without managing clients.

    Args:
        prompt: The prompt to send
        model: Model to use (default: Qwen3-Coder)

    Returns:
        The AI response as a string

    Example:
        response = simple_query("What is 2+2?")
        print(response)  # "4"
    """
    ensure_iflow_api_key()
    return simple_query_sync(prompt, model)

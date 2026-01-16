"""
iFlow SDK Client Configuration
==============================

Functions for creating and configuring the iFlow CLI SDK client.

This module replaces the Claude Agent SDK with iFlow CLI SDK for all AI interactions.
It provides a compatible API layer to minimize changes in existing code.

iFlow CLI SDK uses WebSocket-based Agent Communication Protocol (ACP) for
bidirectional communication with the AI model.
"""

import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional
from enum import Enum

logger = logging.getLogger(__name__)

# =============================================================================
# iFlow SDK Imports (with fallback)
# =============================================================================

try:
    from iflow_sdk import (
        IFlowClient,
        IFlowOptions,
        ApprovalMode,
        query as iflow_query,
        AssistantMessage,
        ToolCallMessage,
        TaskFinishMessage,
        CreateAgentConfig,
    )
    IFLOW_SDK_AVAILABLE = True
except ImportError:
    IFLOW_SDK_AVAILABLE = False
    IFlowClient = None
    IFlowOptions = None
    ApprovalMode = None
    iflow_query = None
    AssistantMessage = None
    ToolCallMessage = None
    TaskFinishMessage = None
    CreateAgentConfig = None
    logger.warning(
        "iflow-cli-sdk not available. Install with: pip install iflow-cli-sdk"
    )


# =============================================================================
# Approval Mode Enum (for compatibility when SDK not available)
# =============================================================================

class IFlowApprovalMode(Enum):
    """Approval modes for iFlow CLI."""
    DEFAULT = "default"  # Model has no permissions, asks for approval
    AUTO_EDIT = "auto_edit"  # Model only has file modification permissions
    YOLO = "yolo"  # Model has maximum permissions
    PLAN = "plan"  # Plan first, then execute


# =============================================================================
# iFlow CLI Path Detection
# =============================================================================

_IFLOW_CLI_CACHE: dict[str, str | None] = {}
_CLI_CACHE_LOCK = threading.Lock()


def _get_iflow_detection_paths() -> dict[str, list[str]]:
    """
    Get all candidate paths for iFlow CLI detection.

    Returns platform-specific paths where iFlow CLI might be installed.

    Returns:
        Dict with 'homebrew', 'platform', and 'nvm' path lists
    """
    home_dir = Path.home()
    is_windows = platform.system() == "Windows"

    homebrew_paths = [
        "/opt/homebrew/bin/iflow",  # Apple Silicon
        "/usr/local/bin/iflow",  # Intel Mac
    ]

    if is_windows:
        platform_paths = [
            str(home_dir / "AppData" / "Local" / "Programs" / "iflow" / "iflow.exe"),
            str(home_dir / "AppData" / "Roaming" / "npm" / "iflow.cmd"),
            str(home_dir / ".local" / "bin" / "iflow.exe"),
            "C:\\Program Files\\iFlow\\iflow.exe",
            "C:\\Program Files (x86)\\iFlow\\iflow.exe",
        ]
    else:
        platform_paths = [
            str(home_dir / ".local" / "bin" / "iflow"),
            str(home_dir / "bin" / "iflow"),
        ]

    nvm_versions_dir = str(home_dir / ".nvm" / "versions" / "node")

    return {
        "homebrew": homebrew_paths,
        "platform": platform_paths,
        "nvm_versions_dir": nvm_versions_dir,
    }


def _is_secure_path(path_str: str) -> bool:
    """
    Validate that a path doesn't contain dangerous characters.
    """
    import re

    dangerous_patterns = [
        r'[;&|`${}[\]<>!"^]',
        r"%[^%]+%",
        r"\.\./",
        r"\.\.\\",
        r"[\r\n]",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, path_str):
            return False

    return True


def _validate_iflow_cli(cli_path: str) -> tuple[bool, str | None]:
    """
    Validate that an iFlow CLI path is executable and returns a version.

    Args:
        cli_path: Path to the iFlow CLI executable

    Returns:
        Tuple of (is_valid, version_string or None)
    """
    import re

    if not _is_secure_path(cli_path):
        logger.warning(f"Rejecting insecure iFlow CLI path: {cli_path}")
        return False, None

    try:
        is_windows = platform.system() == "Windows"

        env = os.environ.copy()
        cli_dir = os.path.dirname(cli_path)
        if cli_dir:
            env["PATH"] = cli_dir + os.pathsep + env.get("PATH", "")

        if is_windows and cli_path.lower().endswith((".cmd", ".bat")):
            cmd_exe = os.environ.get("ComSpec") or os.path.join(
                os.environ.get("SystemRoot", "C:\\Windows"), "System32", "cmd.exe"
            )
            cmd_line = f'""{cli_path}" --version"'
            result = subprocess.run(
                [cmd_exe, "/d", "/s", "/c", cmd_line],
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            result = subprocess.run(
                [cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if is_windows else 0,
            )

        if result.returncode == 0:
            output = result.stdout.strip()
            match = re.search(r"(\d+\.\d+\.\d+)", output)
            version = match.group(1) if match else output.split("\n")[0]
            return True, version

        return False, None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"iFlow CLI validation failed for {cli_path}: {e}")
        return False, None


def find_iflow_cli() -> str | None:
    """
    Find the iFlow CLI binary path.

    Uses cross-platform detection with the following priority:
    1. IFLOW_CLI_PATH environment variable (user override)
    2. shutil.which() - system PATH lookup
    3. Homebrew paths (macOS)
    4. NVM paths (Unix - checks Node.js version manager)
    5. Platform-specific standard locations

    Returns:
        Path to iFlow CLI if found and valid, None otherwise
    """
    cache_key = "iflow_cli"
    with _CLI_CACHE_LOCK:
        if cache_key in _IFLOW_CLI_CACHE:
            cached = _IFLOW_CLI_CACHE[cache_key]
            logger.debug(f"Using cached iFlow CLI path: {cached}")
            return cached

    is_windows = platform.system() == "Windows"
    paths = _get_iflow_detection_paths()

    # 1. Check environment variable override
    env_path = os.environ.get("IFLOW_CLI_PATH")
    if env_path:
        if Path(env_path).exists():
            valid, version = _validate_iflow_cli(env_path)
            if valid:
                logger.info(f"Using IFLOW_CLI_PATH: {env_path} (v{version})")
                with _CLI_CACHE_LOCK:
                    _IFLOW_CLI_CACHE[cache_key] = env_path
                return env_path
        logger.warning(f"IFLOW_CLI_PATH is set but invalid: {env_path}")

    # 2. Try shutil.which()
    which_path = shutil.which("iflow")
    if which_path:
        valid, version = _validate_iflow_cli(which_path)
        if valid:
            logger.info(f"Found iFlow CLI in PATH: {which_path} (v{version})")
            with _CLI_CACHE_LOCK:
                _IFLOW_CLI_CACHE[cache_key] = which_path
            return which_path

    # 3. Homebrew paths (macOS)
    if platform.system() == "Darwin":
        for hb_path in paths["homebrew"]:
            if Path(hb_path).exists():
                valid, version = _validate_iflow_cli(hb_path)
                if valid:
                    logger.info(f"Found iFlow CLI (Homebrew): {hb_path} (v{version})")
                    with _CLI_CACHE_LOCK:
                        _IFLOW_CLI_CACHE[cache_key] = hb_path
                    return hb_path

    # 4. NVM paths (Unix only)
    if not is_windows:
        nvm_dir = Path(paths["nvm_versions_dir"])
        if nvm_dir.exists():
            try:
                version_dirs = []
                for entry in nvm_dir.iterdir():
                    if entry.is_dir() and entry.name.startswith("v"):
                        try:
                            parts = entry.name[1:].split(".")
                            if len(parts) == 3:
                                version_dirs.append(
                                    (tuple(int(p) for p in parts), entry.name)
                                )
                        except ValueError:
                            continue

                version_dirs.sort(reverse=True)

                for _, version_name in version_dirs:
                    nvm_iflow = nvm_dir / version_name / "bin" / "iflow"
                    if nvm_iflow.exists():
                        valid, version = _validate_iflow_cli(str(nvm_iflow))
                        if valid:
                            logger.info(
                                f"Found iFlow CLI (NVM): {nvm_iflow} (v{version})"
                            )
                            with _CLI_CACHE_LOCK:
                                _IFLOW_CLI_CACHE[cache_key] = str(nvm_iflow)
                            return str(nvm_iflow)
            except OSError as e:
                logger.debug(f"Error scanning NVM directory: {e}")

    # 5. Platform-specific standard locations
    for plat_path in paths["platform"]:
        if Path(plat_path).exists():
            valid, version = _validate_iflow_cli(plat_path)
            if valid:
                logger.info(f"Found iFlow CLI: {plat_path} (v{version})")
                with _CLI_CACHE_LOCK:
                    _IFLOW_CLI_CACHE[cache_key] = plat_path
                return plat_path

    # Not found
    logger.warning(
        "iFlow CLI not found. Install with: npm install -g @iflow-ai/iflow-cli"
    )
    with _CLI_CACHE_LOCK:
        _IFLOW_CLI_CACHE[cache_key] = None
    return None


def clear_iflow_cli_cache() -> None:
    """Clear the iFlow CLI path cache, forcing re-detection on next call."""
    with _CLI_CACHE_LOCK:
        _IFLOW_CLI_CACHE.clear()
    logger.debug("iFlow CLI cache cleared")


# =============================================================================
# iFlow Settings Management
# =============================================================================

def get_iflow_settings_path() -> Path:
    """Get the path to iFlow settings file."""
    return Path.home() / ".iflow" / "settings.json"


def load_iflow_settings() -> dict[str, Any]:
    """
    Load iFlow settings from ~/.iflow/settings.json.

    Returns:
        Settings dictionary or empty dict if not found
    """
    settings_path = get_iflow_settings_path()
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load iFlow settings: {e}")
    return {}


def save_iflow_settings(settings: dict[str, Any]) -> bool:
    """
    Save iFlow settings to ~/.iflow/settings.json.

    Args:
        settings: Settings dictionary to save

    Returns:
        True if saved successfully, False otherwise
    """
    settings_path = get_iflow_settings_path()
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Failed to save iFlow settings: {e}")
        return False


# =============================================================================
# iFlow Client Wrapper (Compatible API)
# =============================================================================

class IFlowClientWrapper:
    """
    Wrapper around iFlow SDK client providing a compatible API.

    This class provides an interface similar to the old Claude SDK client
    to minimize changes in existing code.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "Qwen3-Coder",
        base_url: str = "https://apis.iflow.cn/v1",
        approval_mode: str = "yolo",
        allowed_tools: list[str] | None = None,
        working_directory: str | None = None,
        **kwargs,
    ):
        """
        Initialize iFlow client wrapper.

        Args:
            api_key: iFlow API key (or from env/settings)
            model: Model name (default: Qwen3-Coder)
            base_url: API base URL
            approval_mode: One of 'default', 'auto_edit', 'yolo', 'plan'
            allowed_tools: List of allowed tools
            working_directory: Working directory for the agent
        """
        self.api_key = api_key or self._get_api_key()
        self.model = model
        self.base_url = base_url
        self.approval_mode = approval_mode
        self.allowed_tools = allowed_tools or []
        self.working_directory = working_directory
        self._client: Optional[IFlowClient] = None
        self._options_kwargs = kwargs

    def _get_api_key(self) -> str | None:
        """Get API key from environment or settings."""
        # Try environment variable first
        api_key = os.environ.get("IFLOW_API_KEY")
        if api_key:
            return api_key

        # Try settings file
        settings = load_iflow_settings()
        return settings.get("apiKey")

    def _get_approval_mode(self):
        """Convert string approval mode to SDK enum."""
        if not IFLOW_SDK_AVAILABLE or ApprovalMode is None:
            return None

        mode_map = {
            "default": ApprovalMode.DEFAULT,
            "auto_edit": ApprovalMode.AUTO_EDIT,
            "yolo": ApprovalMode.YOLO,
            "plan": ApprovalMode.PLAN,
        }
        return mode_map.get(self.approval_mode.lower(), ApprovalMode.YOLO)

    async def __aenter__(self):
        """Async context manager entry."""
        if not IFLOW_SDK_AVAILABLE:
            raise RuntimeError(
                "iflow-cli-sdk not available. Install with: pip install iflow-cli-sdk"
            )

        options = IFlowOptions(
            approval_mode=self._get_approval_mode(),
            auto_start_process=True,
            **self._options_kwargs,
        )
        self._client = IFlowClient(options)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    async def send_message(self, message: str) -> None:
        """
        Send a message to the AI agent.

        Args:
            message: The message to send
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        await self._client.send_message(message)

    async def receive_messages(self) -> AsyncIterator[Any]:
        """
        Receive messages from the AI agent.

        Yields:
            Message objects (AssistantMessage, ToolCallMessage, TaskFinishMessage, etc.)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        async for message in self._client.receive_messages():
            yield message

    async def query(self, prompt: str) -> str:
        """
        Simple query interface for single-turn interactions.

        Args:
            prompt: The prompt to send

        Returns:
            The AI response as a string
        """
        if not IFLOW_SDK_AVAILABLE or iflow_query is None:
            raise RuntimeError(
                "iflow-cli-sdk not available. Install with: pip install iflow-cli-sdk"
            )
        return await iflow_query(prompt)


# =============================================================================
# Synchronous Wrapper (for backward compatibility)
# =============================================================================

class SyncIFlowClient:
    """
    Synchronous wrapper around IFlowClientWrapper.

    Provides a synchronous API for code that cannot use async/await.
    """

    def __init__(self, **kwargs):
        """Initialize with same arguments as IFlowClientWrapper."""
        self._async_client = IFlowClientWrapper(**kwargs)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create event loop."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def __enter__(self):
        """Sync context manager entry."""
        loop = self._get_loop()
        loop.run_until_complete(self._async_client.__aenter__())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        loop = self._get_loop()
        loop.run_until_complete(self._async_client.__aexit__(exc_type, exc_val, exc_tb))

    def send_message(self, message: str) -> None:
        """Send a message synchronously."""
        loop = self._get_loop()
        loop.run_until_complete(self._async_client.send_message(message))

    def receive_messages(self):
        """Receive messages synchronously (generator)."""
        loop = self._get_loop()

        async def collect_messages():
            messages = []
            async for msg in self._async_client.receive_messages():
                messages.append(msg)
            return messages

        messages = loop.run_until_complete(collect_messages())
        for msg in messages:
            yield msg

    def query(self, prompt: str) -> str:
        """Simple query synchronously."""
        loop = self._get_loop()
        return loop.run_until_complete(self._async_client.query(prompt))


# =============================================================================
# Factory Functions
# =============================================================================

def create_iflow_client(
    project_dir: Path | None = None,
    spec_dir: Path | None = None,
    model: str = "Qwen3-Coder",
    agent_type: str = "coder",
    approval_mode: str = "yolo",
    **kwargs,
) -> IFlowClientWrapper:
    """
    Create a configured iFlow client.

    This is the main factory function for creating iFlow clients.
    It replaces the old create_client() function from Claude SDK.

    Args:
        project_dir: Path to the project directory
        spec_dir: Path to the spec directory
        model: Model name to use
        agent_type: Type of agent (planner, coder, qa_reviewer, qa_fixer)
        approval_mode: Approval mode (default, auto_edit, yolo, plan)
        **kwargs: Additional options passed to IFlowClientWrapper

    Returns:
        Configured IFlowClientWrapper instance
    """
    working_directory = str(project_dir) if project_dir else None

    return IFlowClientWrapper(
        model=model,
        approval_mode=approval_mode,
        working_directory=working_directory,
        **kwargs,
    )


def create_simple_iflow_client(
    model: str = "Qwen3-Coder",
    **kwargs,
) -> SyncIFlowClient:
    """
    Create a simple synchronous iFlow client for single-turn operations.

    Args:
        model: Model name to use
        **kwargs: Additional options

    Returns:
        SyncIFlowClient instance
    """
    return SyncIFlowClient(model=model, **kwargs)


# =============================================================================
# Utility Functions
# =============================================================================

async def simple_query(prompt: str, model: str = "Qwen3-Coder") -> str:
    """
    Simple async query function.

    Args:
        prompt: The prompt to send
        model: Model name to use

    Returns:
        The AI response as a string
    """
    if not IFLOW_SDK_AVAILABLE or iflow_query is None:
        raise RuntimeError(
            "iflow-cli-sdk not available. Install with: pip install iflow-cli-sdk"
        )
    return await iflow_query(prompt)


def simple_query_sync(prompt: str, model: str = "Qwen3-Coder") -> str:
    """
    Simple synchronous query function.

    Args:
        prompt: The prompt to send
        model: Model name to use

    Returns:
        The AI response as a string
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(simple_query(prompt, model))
    finally:
        loop.close()


def is_iflow_sdk_available() -> bool:
    """Check if iFlow SDK is available."""
    return IFLOW_SDK_AVAILABLE


def require_iflow_sdk() -> None:
    """Raise error if iFlow SDK is not available."""
    if not IFLOW_SDK_AVAILABLE:
        raise RuntimeError(
            "iflow-cli-sdk is required but not installed. "
            "Install with: pip install iflow-cli-sdk"
        )

"""
Authentication helpers for Auto-iFlow.

Provides centralized authentication for iFlow CLI SDK with fallback support
for multiple sources: environment variables, settings file, and legacy Claude tokens.

iFlow uses API keys instead of OAuth tokens, making authentication simpler.
"""

import json
import os
import platform
import subprocess
from pathlib import Path

# Priority order for auth token/key resolution
# iFlow uses API keys, but we also support legacy Claude tokens for migration
AUTH_KEY_ENV_VARS = [
    "IFLOW_API_KEY",  # Primary: iFlow API key
    # Legacy Claude support (for migration period)
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_AUTH_TOKEN",
]

# Environment variables to pass through to SDK subprocess
SDK_ENV_VARS = [
    # iFlow configuration
    "IFLOW_API_KEY",
    "IFLOW_BASE_URL",
    "IFLOW_MODEL",
    # Legacy Anthropic configuration (for compatibility)
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    # Model overrides
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    # SDK behavior configuration
    "NO_PROXY",
    "DISABLE_TELEMETRY",
    "DISABLE_COST_WARNINGS",
    "API_TIMEOUT_MS",
    # Windows-specific: Git Bash path
    "IFLOW_GIT_BASH_PATH",
    "CLAUDE_CODE_GIT_BASH_PATH",  # Legacy
]


# =============================================================================
# iFlow Settings File
# =============================================================================

def get_iflow_settings_path() -> Path:
    """Get the path to iFlow settings file."""
    return Path.home() / ".iflow" / "settings.json"


def get_api_key_from_iflow_settings() -> str | None:
    """
    Get API key from iFlow settings file (~/.iflow/settings.json).

    Returns:
        API key string if found, None otherwise
    """
    settings_path = get_iflow_settings_path()
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("apiKey")
        except (json.JSONDecodeError, IOError):
            pass
    return None


# =============================================================================
# Legacy Claude Credential Support (for migration)
# =============================================================================

def get_token_from_keychain() -> str | None:
    """
    Get authentication token from system credential store (legacy Claude support).

    Reads Claude Code credentials from:
    - macOS: Keychain
    - Windows: Credential Manager
    - Linux: Not yet supported (use env var)

    Returns:
        Token string if found, None otherwise
    """
    system = platform.system()

    if system == "Darwin":
        return _get_token_from_macos_keychain()
    elif system == "Windows":
        return _get_token_from_windows_credential_files()
    else:
        return None


def _get_token_from_macos_keychain() -> str | None:
    """Get token from macOS Keychain (legacy Claude support)."""
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                "Claude Code-credentials",
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return None

        credentials_json = result.stdout.strip()
        if not credentials_json:
            return None

        data = json.loads(credentials_json)
        token = data.get("claudeAiOauth", {}).get("accessToken")

        if not token:
            return None

        if not token.startswith("sk-ant-oat01-"):
            return None

        return token

    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, Exception):
        return None


def _get_token_from_windows_credential_files() -> str | None:
    """Get token from Windows credential files (legacy Claude support)."""
    try:
        cred_paths = [
            os.path.expandvars(r"%USERPROFILE%\.claude\.credentials.json"),
            os.path.expandvars(r"%USERPROFILE%\.claude\credentials.json"),
            os.path.expandvars(r"%LOCALAPPDATA%\Claude\credentials.json"),
            os.path.expandvars(r"%APPDATA%\Claude\credentials.json"),
        ]

        for cred_path in cred_paths:
            if os.path.exists(cred_path):
                with open(cred_path, encoding="utf-8") as f:
                    data = json.load(f)
                    token = data.get("claudeAiOauth", {}).get("accessToken")
                    if token and token.startswith("sk-ant-oat01-"):
                        return token

        return None

    except (json.JSONDecodeError, KeyError, FileNotFoundError, Exception):
        return None


# =============================================================================
# Main Authentication Functions
# =============================================================================

def get_iflow_api_key() -> str | None:
    """
    Get iFlow API key from multiple sources.

    Checks in priority order:
    1. IFLOW_API_KEY environment variable
    2. ~/.iflow/settings.json file
    3. Legacy Claude tokens (for migration)

    Returns:
        API key string if found, None otherwise
    """
    # 1. Check IFLOW_API_KEY environment variable
    api_key = os.environ.get("IFLOW_API_KEY")
    if api_key:
        return api_key

    # 2. Check iFlow settings file
    api_key = get_api_key_from_iflow_settings()
    if api_key:
        return api_key

    # 3. Legacy: Check Claude tokens (for migration period)
    for var in AUTH_KEY_ENV_VARS[1:]:  # Skip IFLOW_API_KEY
        token = os.environ.get(var)
        if token:
            return token

    # 4. Legacy: Check system credential store
    return get_token_from_keychain()


def get_auth_token() -> str | None:
    """
    Get authentication token/key (alias for get_iflow_api_key).

    This function is kept for backward compatibility.

    Returns:
        API key/token string if found, None otherwise
    """
    return get_iflow_api_key()


def get_auth_token_source() -> str | None:
    """Get the name of the source that provided the auth token/key."""
    # Check IFLOW_API_KEY first
    if os.environ.get("IFLOW_API_KEY"):
        return "IFLOW_API_KEY"

    # Check iFlow settings file
    if get_api_key_from_iflow_settings():
        return "~/.iflow/settings.json"

    # Check legacy environment variables
    for var in AUTH_KEY_ENV_VARS[1:]:
        if os.environ.get(var):
            return var

    # Check if token came from system credential store
    if get_token_from_keychain():
        system = platform.system()
        if system == "Darwin":
            return "macOS Keychain (legacy)"
        elif system == "Windows":
            return "Windows Credential Files (legacy)"
        else:
            return "System Credential Store (legacy)"

    return None


def require_auth_token() -> str:
    """
    Get authentication token/key or raise ValueError.

    Raises:
        ValueError: If no API key is found in any supported source
    """
    api_key = get_iflow_api_key()
    if not api_key:
        error_msg = (
            "No iFlow API key found.\n\n"
            "Auto-iFlow requires an iFlow API key for authentication.\n"
            "iFlow is FREE - get your API key at https://iflow.cn\n\n"
        )
        system = platform.system()
        error_msg += (
            "To authenticate:\n"
            "  Option 1: Run 'iflow' and follow the login prompts\n"
            "  Option 2: Set IFLOW_API_KEY in your .env file\n"
            "  Option 3: Add apiKey to ~/.iflow/settings.json\n\n"
            "Get your free API key:\n"
            "  1. Register at https://iflow.cn\n"
            "  2. Go to profile settings\n"
            "  3. Click 'Reset' to generate a new API key"
        )
        raise ValueError(error_msg)
    return api_key


def require_iflow_api_key() -> str:
    """
    Get iFlow API key or raise ValueError (alias for require_auth_token).

    Raises:
        ValueError: If no API key is found
    """
    return require_auth_token()


def _find_git_bash_path() -> str | None:
    """
    Find git-bash (bash.exe) path on Windows.

    Uses 'where git' to find git.exe, then derives bash.exe location from it.

    Returns:
        Full path to bash.exe if found, None otherwise
    """
    if platform.system() != "Windows":
        return None

    # Check both iFlow and legacy Claude env vars
    for env_var in ["IFLOW_GIT_BASH_PATH", "CLAUDE_CODE_GIT_BASH_PATH"]:
        existing = os.environ.get(env_var)
        if existing and os.path.exists(existing):
            return existing

    git_path = None

    # Method 1: Use 'where' command to find git.exe
    try:
        result = subprocess.run(
            ["where.exe", "git"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )

        if result.returncode == 0 and result.stdout.strip():
            git_paths = result.stdout.strip().splitlines()
            if git_paths:
                git_path = git_paths[0].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        pass

    # Method 2: Check common installation paths
    if not git_path:
        common_git_paths = [
            os.path.expandvars(r"%PROGRAMFILES%\Git\cmd\git.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Git\bin\git.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Git\cmd\git.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
        ]
        for path in common_git_paths:
            if os.path.exists(path):
                git_path = path
                break

    if not git_path:
        return None

    # Derive bash.exe location from git.exe location
    git_dir = os.path.dirname(git_path)
    git_parent = os.path.dirname(git_dir)
    git_grandparent = os.path.dirname(git_parent)

    possible_bash_paths = [
        os.path.join(git_parent, "bin", "bash.exe"),
        os.path.join(git_dir, "bash.exe"),
        os.path.join(git_grandparent, "bin", "bash.exe"),
    ]

    for bash_path in possible_bash_paths:
        if os.path.exists(bash_path):
            return bash_path

    return None


def get_sdk_env_vars() -> dict[str, str]:
    """
    Get environment variables to pass to SDK.

    Collects relevant env vars that should be passed through to the
    iflow-cli-sdk subprocess.

    On Windows, auto-detects git-bash path if not already set.

    Returns:
        Dict of env var name -> value for non-empty vars
    """
    env = {}
    for var in SDK_ENV_VARS:
        value = os.environ.get(var)
        if value:
            env[var] = value

    # On Windows, auto-detect git-bash path if not already set
    if platform.system() == "Windows":
        if "IFLOW_GIT_BASH_PATH" not in env and "CLAUDE_CODE_GIT_BASH_PATH" not in env:
            bash_path = _find_git_bash_path()
            if bash_path:
                env["IFLOW_GIT_BASH_PATH"] = bash_path

    return env


def ensure_iflow_api_key() -> None:
    """
    Ensure IFLOW_API_KEY is set in environment.

    If not set but API key is available from other sources,
    copies the value to IFLOW_API_KEY for SDK compatibility.
    """
    if os.environ.get("IFLOW_API_KEY"):
        return

    api_key = get_iflow_api_key()
    if api_key:
        os.environ["IFLOW_API_KEY"] = api_key


# Legacy alias for backward compatibility
def ensure_claude_code_oauth_token() -> None:
    """
    Legacy function - now calls ensure_iflow_api_key().

    Kept for backward compatibility during migration.
    """
    ensure_iflow_api_key()

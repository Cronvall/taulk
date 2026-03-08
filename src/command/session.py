"""Claude Code SDK session management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolPermissionContext,
    ToolUseBlock,
)


def _make_path_guard(allowed_root: str):
    """Return a can_use_tool callback that blocks file access outside allowed_root."""
    root = os.path.realpath(allowed_root)

    async def guard(
        tool_name: str,
        input_data: dict,
        context: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        # Tools that carry a file path
        path_key = None
        if tool_name in ("Read", "Write", "Edit"):
            path_key = "file_path"
        elif tool_name == "Glob":
            path_key = "path"
        elif tool_name == "Grep":
            path_key = "path"

        if path_key and path_key in input_data:
            target = os.path.realpath(input_data[path_key])
            if not target.startswith(root + os.sep) and target != root:
                return PermissionResultDeny(
                    message=f"Access denied: {input_data[path_key]} is outside the allowed directory ({allowed_root})"
                )

        # Block bash commands that navigate outside the directory
        if tool_name == "Bash":
            command = input_data.get("command", "")
            # Block explicit cd to outside directories
            if "cd " in command:
                # Extract cd targets naively — not bulletproof but catches common cases
                for part in command.split("&&"):
                    part = part.strip()
                    if part.startswith("cd "):
                        target_dir = part[3:].strip().strip("'\"")
                        # Resolve relative to allowed root
                        resolved = os.path.realpath(os.path.join(root, target_dir))
                        if not resolved.startswith(root + os.sep) and resolved != root:
                            return PermissionResultDeny(
                                message=f"Access denied: cannot cd to {target_dir} (outside {allowed_root})"
                            )

        return PermissionResultAllow()

    return guard


class ClaudeSession:
    """Manages a multi-turn conversation with Claude Code via the SDK."""

    def __init__(self, cwd: str = ".", permission_mode: str = "default") -> None:
        self.cwd = cwd
        self.permission_mode = permission_mode
        self._client: ClaudeSDKClient | None = None

    async def start(self) -> None:
        """Initialize the SDK client."""
        # Ensure the working directory exists
        Path(self.cwd).mkdir(parents=True, exist_ok=True)

        options = ClaudeAgentOptions(
            cwd=self.cwd,
            permission_mode=self.permission_mode,
            can_use_tool=_make_path_guard(self.cwd),
        )
        self._client = ClaudeSDKClient(options=options)
        await self._client.__aenter__()

    async def stop(self) -> None:
        """Shut down the SDK client."""
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def send(self, text: str) -> AsyncIterator[AssistantMessage | ResultMessage]:
        """Send a prompt and yield response messages."""
        if self._client is None:
            raise RuntimeError("Session not started. Call start() first.")
        await self._client.query(text)
        async for message in self._client.receive_response():
            yield message

    async def set_permission_mode(self, mode: str) -> None:
        """Change the permission mode (e.g. 'default', 'plan', 'acceptEdits')."""
        if self._client is not None:
            self._client.set_permission_mode(mode)
        self.permission_mode = mode

    async def interrupt(self) -> None:
        """Send an interrupt signal to abort the current response.

        The session remains valid for future queries after interruption.
        """
        if self._client is not None:
            await self._client.interrupt()

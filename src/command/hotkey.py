"""Global hotkey listener bridged to asyncio."""

from __future__ import annotations

import asyncio
import threading
from typing import Callable

from pynput import keyboard


class HotkeyListener:
    """Listens for press/release of a configurable key and signals asyncio events."""

    def __init__(self, hotkey: str = "Key.alt_r") -> None:
        self._hotkey_str = hotkey
        self._target_key = self._parse_key(hotkey)
        self._listener: keyboard.Listener | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Asyncio events set from the pynput thread
        self.pressed = asyncio.Event()
        self.released = asyncio.Event()

        self._is_held = False

    @staticmethod
    def _parse_key(key_str: str) -> keyboard.Key | keyboard.KeyCode:
        """Parse a key string like 'Key.alt_r' or 'a' into a pynput key."""
        if key_str.startswith("Key."):
            attr = key_str[4:]
            return getattr(keyboard.Key, attr)
        return keyboard.KeyCode.from_char(key_str)

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key == self._target_key and not self._is_held:
            self._is_held = True
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self.pressed.set)

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key == self._target_key and self._is_held:
            self._is_held = False
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self.released.set)

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the keyboard listener. Must be called from the main thread."""
        self._loop = loop
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        """Stop the keyboard listener."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    @property
    def is_held(self) -> bool:
        """Whether the hotkey is currently being held down."""
        return self._is_held

    def reset(self) -> None:
        """Clear both events so we can wait for the next press/release cycle."""
        self.pressed.clear()
        self.released.clear()

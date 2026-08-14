"""Pydantic schemas for MCP tool inputs and outputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Strategy = Literal[
    "id", "css", "xpath", "link_text", "partial_link_text",
    "tag_name", "class_name", "name",
]
Context = Literal["chrome", "content"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Process ---
class LaunchInput(_Model):
    profile: str
    marionette_port: int = 2828
    wait_ready: bool = True
    ready_timeout: float = 30.0


class LaunchOutput(_Model):
    pid: int
    port: int
    connected: bool


class TerminateInput(_Model):
    pid: int | None = None


class TerminateOutput(_Model):
    stopped: bool


class StatusOutput(_Model):
    running: bool
    pid: int | None
    port: int
    connected: bool


# --- Extensions ---
class ExtensionInstallInput(_Model):
    xpi_path: str
    temporary: bool = True


class ExtensionInstallOutput(_Model):
    addon_id: str


class ExtensionUninstallInput(_Model):
    addon_id: str


class ExtensionUninstallOutput(_Model):
    removed: bool


class ExtensionReloadInput(_Model):
    addon_id: str
    xpi_path: str


class ExtensionReloadOutput(_Model):
    addon_id: str
    reloaded: bool


class AddonInfo(_Model):
    id: str
    name: str
    version: str
    enabled: bool
    temporary: bool


# --- UI ---
class FindElementInput(_Model):
    strategy: Strategy
    selector: str
    context: Context = "chrome"
    timeout: float = 5.0


class FindElementOutput(_Model):
    element_id: str


class FindElementsOutput(_Model):
    element_ids: list[str]


class ClickInput(_Model):
    element_id: str


class TypeTextInput(_Model):
    element_id: str
    text: str
    clear: bool = False


class ElementIdInput(_Model):
    element_id: str


class GetAttributeInput(_Model):
    element_id: str
    name: str


class GetAttributeOutput(_Model):
    value: str | None


class GetPropertyOutput(_Model):
    value: Any


class TextOutput(_Model):
    text: str


class VisibleOutput(_Model):
    visible: bool


class WindowInfo(_Model):
    handle: str
    title: str
    url: str


class SwitchWindowInput(_Model):
    handle: str


class WaitForElementInput(_Model):
    strategy: Strategy
    selector: str
    context: Context = "chrome"
    timeout: float = 10.0
    visible: bool = True


# --- Keys ---
class SendKeysInput(_Model):
    keys: str
    element_id: str | None = None


class SendHotkeyInput(_Model):
    chord: str = Field(min_length=1)
    element_id: str | None = None


# --- Scripts ---
class ExecuteScriptInput(_Model):
    script: str
    args: list[Any] = Field(default_factory=list)
    context: Context = "chrome"
    async_: bool = False
    timeout: float = 30.0


class ScriptResult(_Model):
    result: Any


class WaitForConditionInput(_Model):
    script: str
    args: list[Any] = Field(default_factory=list)
    context: Context = "chrome"
    timeout: float = 30.0
    poll_interval: float = 0.5


# --- Diagnostics ---
class ScreenshotInput(_Model):
    element_id: str | None = None
    format: Literal["png", "jpeg"] = "png"
    full: bool = False


class ScreenshotOutput(_Model):
    data_base64: str
    format: str


class PageSourceInput(_Model):
    context: Context = "content"


class PageSourceOutput(_Model):
    source: str


class UrlOutput(_Model):
    url: str


class TitleOutput(_Model):
    title: str


class ConsoleLogsInput(_Model):
    clear: bool = False
    level: str | None = None


class ConsoleLogEntry(_Model):
    level: str
    message: str
    timestamp: float
    source: str | None = None


class MarionetteLogOutput(_Model):
    log: str
    available: bool


class EmptyOutput(_Model):
    pass

"""Error hierarchy for tb-marionette-mcp."""

from __future__ import annotations

from typing import Any


class TbMcpError(Exception):
    code: str = "generic"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details or {}


class NotConnectedError(TbMcpError):
    code = "not_connected"


class LaunchError(TbMcpError):
    code = "launch_failed"


class MarionetteWireError(TbMcpError):
    code = "wire_error"


class ElementNotFoundError(TbMcpError):
    code = "element_not_found"


class ExtensionInstallError(TbMcpError):
    code = "extension_install_failed"


class TimeoutError(TbMcpError):
    code = "timeout"


class InvalidArgumentError(TbMcpError):
    code = "invalid_argument"

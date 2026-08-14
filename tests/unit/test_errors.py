from tb_marionette_mcp.errors import (
    ElementNotFoundError,
    ExtensionInstallError,
    InvalidArgumentError,
    LaunchError,
    MarionetteWireError,
    NotConnectedError,
    TbMcpError,
)
from tb_marionette_mcp.errors import (
    TimeoutError as TbTimeoutError,
)


def test_base_error_has_code_and_message():
    err = TbMcpError("boom", code="generic", details={"x": 1})
    assert err.code == "generic"
    assert err.message == "boom"
    assert err.details == {"x": 1}
    assert str(err) == "boom"


def test_subclass_codes():
    assert NotConnectedError("x").code == "not_connected"
    assert LaunchError("x").code == "launch_failed"
    assert MarionetteWireError("x").code == "wire_error"
    assert ElementNotFoundError("x").code == "element_not_found"
    assert ExtensionInstallError("x").code == "extension_install_failed"
    assert TbTimeoutError("x").code == "timeout"
    assert InvalidArgumentError("x").code == "invalid_argument"

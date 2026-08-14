import pytest
from pydantic import ValidationError

from tb_marionette_mcp.models import (
    ClickInput,
    ExtensionInstallInput,
    FindElementInput,
    LaunchInput,
    SendHotkeyInput,
    TypeTextInput,
)


def test_launch_defaults():
    m = LaunchInput(profile="test-profile")
    assert m.marionette_port == 2828
    assert m.wait_ready is True
    assert m.ready_timeout == 30.0


def test_launch_missing_profile():
    with pytest.raises(ValidationError):
        LaunchInput()


def test_find_element_strategy_enum():
    m = FindElementInput(strategy="css", selector="#foo")
    assert m.context == "chrome"
    with pytest.raises(ValidationError):
        FindElementInput(strategy="jquery", selector="#foo")


def test_click_requires_id():
    with pytest.raises(ValidationError):
        ClickInput()


def test_type_text_defaults():
    m = TypeTextInput(element_id="abc", text="hello")
    assert m.clear is False


def test_hotkey_input():
    m = SendHotkeyInput(chord="Ctrl+Shift+N")
    assert m.chord == "Ctrl+Shift+N"


def test_extension_install_defaults():
    m = ExtensionInstallInput(xpi_path="/tmp/x.xpi")
    assert m.temporary is True

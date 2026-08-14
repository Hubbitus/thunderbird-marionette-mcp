"""Test server registration of all tools."""

from __future__ import annotations

from tb_marionette_mcp.server import build_server


def test_server_registers_expected_tools() -> None:
    server = build_server()
    tool_names = {t.name for t in server._tool_manager.list_tools()}
    expected = {
        "thunderbird_launch",
        "thunderbird_terminate",
        "thunderbird_status",
        "extension_install",
        "extension_uninstall",
        "extension_reload",
        "extension_list",
        "find_element",
        "find_elements",
        "click",
        "type_text",
        "get_text",
        "get_attribute",
        "get_property",
        "is_displayed",
        "list_windows",
        "switch_to_window",
        "switch_to_frame",
        "switch_to_default",
        "wait_for_element",
        "send_keys",
        "send_hotkey",
        "execute_script",
        "wait_for_condition",
        "screenshot",
        "get_page_source",
        "get_current_url",
        "get_window_title",
        "get_console_logs",
        "get_marionette_log",
    }
    missing = expected - tool_names
    assert not missing, f"missing tools: {missing}"
    assert len(tool_names) >= 30

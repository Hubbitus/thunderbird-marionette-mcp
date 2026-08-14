"""FastMCP server entry point and tool registration."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from tb_marionette_mcp.logging_ import configure_logging, get_logger
from tb_marionette_mcp.tools import (
    diagnostic_tools,
    extension_tools,
    key_tools,
    process_tools,
    script_tools,
    ui_tools,
)


def build_server() -> FastMCP:
    """Build and register all 30 tools into FastMCP server."""
    server = FastMCP("tb-marionette-mcp")

    # Process tools (3)
    server.add_tool(process_tools.thunderbird_launch)
    server.add_tool(process_tools.thunderbird_terminate)
    server.add_tool(process_tools.thunderbird_status)

    # Extension tools (4)
    server.add_tool(extension_tools.extension_install)
    server.add_tool(extension_tools.extension_uninstall)
    server.add_tool(extension_tools.extension_reload)
    server.add_tool(extension_tools.extension_list)

    # UI tools (13)
    server.add_tool(ui_tools.find_element)
    server.add_tool(ui_tools.find_elements)
    server.add_tool(ui_tools.click)
    server.add_tool(ui_tools.type_text)
    server.add_tool(ui_tools.get_text)
    server.add_tool(ui_tools.get_attribute)
    server.add_tool(ui_tools.get_property)
    server.add_tool(ui_tools.is_displayed)
    server.add_tool(ui_tools.list_windows)
    server.add_tool(ui_tools.switch_to_window)
    server.add_tool(ui_tools.switch_to_frame)
    server.add_tool(ui_tools.switch_to_default)
    server.add_tool(ui_tools.wait_for_element)

    # Key tools (2)
    server.add_tool(key_tools.send_keys)
    server.add_tool(key_tools.send_hotkey)

    # Script tools (2)
    server.add_tool(script_tools.execute_script)
    server.add_tool(script_tools.wait_for_condition)

    # Diagnostic tools (6)
    server.add_tool(diagnostic_tools.screenshot)
    server.add_tool(diagnostic_tools.get_page_source)
    server.add_tool(diagnostic_tools.get_current_url)
    server.add_tool(diagnostic_tools.get_window_title)
    server.add_tool(diagnostic_tools.get_console_logs)
    server.add_tool(diagnostic_tools.get_marionette_log)

    return server


def main() -> None:
    """Start FastMCP server with stdio transport."""
    configure_logging()
    log = get_logger(__name__)
    log.info("startup")
    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

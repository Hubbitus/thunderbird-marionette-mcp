from unittest.mock import patch


def test_main_module_imports_main():
    from tb_marionette_mcp import __main__ as mod
    from tb_marionette_mcp.server import main
    assert mod.main is main


def test_server_main_runs():
    from tb_marionette_mcp import server
    with patch.object(server, "configure_logging") as cfg, \
         patch.object(server, "build_server") as build:
        fake = build.return_value
        server.main()
    cfg.assert_called_once()
    fake.run.assert_called_once_with(transport="stdio")

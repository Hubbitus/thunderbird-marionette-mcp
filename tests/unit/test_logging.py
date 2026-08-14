from unittest.mock import patch

from tb_marionette_mcp.logging_ import configure_logging, get_logger


def test_configure_logging_default_level_reads_env(monkeypatch):
    monkeypatch.delenv("TB_MCP_LOG_LEVEL", raising=False)
    with patch("tb_marionette_mcp.logging_.logging.basicConfig") as basic, \
         patch("tb_marionette_mcp.logging_.structlog.configure"):
        configure_logging()
    assert basic.call_args.kwargs["level"] == "INFO"


def test_configure_logging_debug_level(monkeypatch):
    monkeypatch.setenv("TB_MCP_LOG_LEVEL", "debug")
    with patch("tb_marionette_mcp.logging_.logging.basicConfig") as basic, \
         patch("tb_marionette_mcp.logging_.structlog.configure"):
        configure_logging()
    assert basic.call_args.kwargs["level"] == "DEBUG"


def test_get_logger_returns_logger_object():
    log = get_logger("test.module")
    # structlog returns a BoundLoggerLazyProxy which has bind/info methods
    assert hasattr(log, "info")
    assert hasattr(log, "bind")

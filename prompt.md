# Проект: thunderbird-marionette-mcp

## Задача

Реализовать MCP-сервер (Model Context Protocol) на **Python**, дающий AI-ассистенту UI-automation доступ к запущенному Thunderbird через **Marionette** протокол.

Пустая ниша: существующие Thunderbird MCP серверы (TKasperczyk/thunderbird-mcp, vitalio-sh/thunderbird-cli, U-C4N, zileo-mcp-thunderbird и др.) все работают через WebExtension API из самой Thunderbird — умеют читать/писать письма, папки, контакты, но **не умеют кликать по UI**, симулировать hotkey, взаимодействовать с popup-окнами сторонних extensions, диалогами настроек. Marionette — родной Gecko automation protocol, даёт полный chrome/content scope, в том числе доступ к WebExt popup DOM.

Основной use case: end-to-end тестирование Thunderbird extensions, где нужно кликнуть по кнопке в extension popup, ввести текст, проверить состояние UI, снять скриншот, симулировать хоткей.

## Технический стек

- **Python** 3.11+ (`uv` для управления окружением)
- **marionette_driver** — официальный Mozilla клиент к Marionette (`pip install marionette_driver`). Есть в PyPI, поддерживается Mozilla, работает и с Firefox, и с Thunderbird (общий Gecko).
- **MCP Python SDK** — `mcp` package (Anthropic official, `pip install mcp`) — реализация MCP протокола на Python. Использовать stdio transport (стандарт для Claude Desktop / Claude Code).
- Запуск Thunderbird: `thunderbird --marionette -P <profile-name> -no-remote` (порт по умолчанию 2828, настраивается через `--marionette-port`)

## Требования

### 1. Управление Thunderbird процессом

- Tool `thunderbird_launch(profile: str, marionette_port: int = 2828, wait_ready: bool = true) → {pid, port, connected: bool}`
  - Запуск с явным профилем, изолированный от основного (пользовательские данные не трогать)
  - Ожидание готовности Marionette listener (`marionette.raise_for_port()`)
  - Возврат pid для последующего terminate
- Tool `thunderbird_terminate(pid: int) → {stopped: bool}`
- Tool `thunderbird_status() → {running: bool, pid: int|null, connected: bool}`
- Autoconnect: если MCP-клиент вызывает любой другой tool без предварительного launch, но TB уже запущен на порту — переиспользовать соединение.

### 2. Установка/удаление расширений

- Tool `extension_install(xpi_path: str, temporary: bool = true) → {addon_id: str}`
  - Через Marionette command `Addon:Install` (аналог `browser.addonManager` в chrome scope)
  - `temporary: true` — установка как "temporary add-on" (для dev, без подписи, слетает при рестарте)
- Tool `extension_uninstall(addon_id: str) → {removed: bool}`
- Tool `extension_reload(addon_id: str) → {reloaded: bool}` — remove + install заново (для dev-cycle)
- Tool `extension_list() → [{id, name, version, enabled, temporary}]`

### 3. UI взаимодействие

- Tool `find_element(strategy: str, selector: str, context: "chrome"|"content" = "chrome", timeout: float = 5.0) → {element_id}`
  - strategy: `id`, `css`, `xpath`, `link_text`, `tag_name`, `class_name`
- Tool `click(element_id: str)`
- Tool `type_text(element_id: str, text: str, clear: bool = false)`
- Tool `get_text(element_id: str) → string`
- Tool `get_attribute(element_id: str, name: str) → string`
- Tool `switch_to_window(handle: str)` + `list_windows() → [{handle, title, url}]`
- Tool `switch_to_frame(element_id: str)` / `switch_to_default()`
- Tool `execute_script(script: str, args: list = [], context: "chrome"|"content" = "chrome") → any`
  - Выполнение произвольного JS с полными chrome-правами (для доступа к `Services`, `Cc/Ci`, `MailServices` и т.д. в chrome context)

### 4. Хоткеи и симуляция клавиш

- Tool `send_keys(keys: str, element_id: str = null)` — глобально или в конкретный элемент
- Tool `send_hotkey(chord: str)` — например `"Ctrl+Shift+N"`; парсер модификаторов
- Формат чорда: пробел/`+` разделитель, ключи как в W3C WebDriver spec

### 5. Скриншоты и state inspection

- Tool `screenshot(element_id: str = null, format: "png"|"jpeg" = "png") → base64` — либо весь экран, либо элемент
- Tool `get_page_source(context: "chrome"|"content" = "content") → string`
- Tool `get_current_url() → string`
- Tool `get_window_title() → string`

### 6. Ожидания

- Tool `wait_for_element(strategy, selector, context, timeout, visible: bool = true) → {element_id}`
- Tool `wait_for_condition(script: str, timeout: float) → any` — polling произвольного JS predicate

### 7. Логирование и диагностика

- Tool `get_console_logs(clear: bool = false) → [{level, message, timestamp, source}]`
  - Через Browser Console API / `Services.console.getMessageArray()`
- Tool `get_marionette_log() → string`

## Архитектура

```
┌──────────────────┐    stdio (MCP)     ┌───────────────────┐   Marionette TCP    ┌──────────────┐
│ Claude Code /    │◄──────────────────►│ Python MCP server │◄───(port 2828)─────►│ Thunderbird  │
│ Claude Desktop   │                    │ marionette_driver │                     │ --marionette │
└──────────────────┘                    └───────────────────┘                     └──────────────┘
```

Один процесс MCP-сервера держит одно живое соединение Marionette. Пересоединение при обрыве. Idle-timeout не нужен (stdio session привязана к клиенту).

### Модули (Python)

```
src/tb_marionette_mcp/
  __init__.py
  server.py              # MCP entry point, tool registrations
  marionette_client.py   # обёртка над marionette_driver с retry/reconnect
  tools/
    process.py           # launch, terminate, status
    extensions.py        # install, uninstall, reload, list
    ui.py                # find, click, type, screenshot
    keys.py              # send_keys, send_hotkey
    scripts.py           # execute_script, wait_for_condition
    diagnostics.py       # logs, screenshots, page_source
  models.py              # pydantic schemas для tool inputs/outputs
tests/
  test_marionette_client.py
  test_tools_*.py
  fixtures/              # test extensions .xpi, test profiles
```

## Требования к качеству

1. **Type hints везде**, `mypy --strict` clean
2. **Pydantic** для validation tool inputs/outputs
3. **pytest** + coverage ≥80% (unit + integration с реальным TB в CI opt-in)
4. **Ruff** для линта и формата (заменяет black+isort+flake8)
5. `pyproject.toml`, `uv` для env, `hatchling` для build
6. **README.md** с:
   - Установка (`uv tool install` или `pip install`)
   - Конфигурация в Claude Desktop / Claude Code (`claude mcp add ...`)
   - Пример: запустить TB, установить extension, кликнуть по кнопке, снять скриншот
   - Раздел Troubleshooting (порт занят, TB не отвечает, extension не устанавливается)
7. **GitHub Actions CI**: lint + type-check + unit tests на push. Integration tests (с TB) — opt-in job (self-hosted runner или ручной trigger)
8. **Логирование** через `structlog` в JSON, level настраивается env-переменной

## Особенности Thunderbird vs Firefox для Marionette

- TB использует другие chrome URIs: главное окно `chrome://messenger/content/messenger.xhtml` вместо `chrome://browser/content/browser.xhtml`
- WebExt popup в TB открывается как отдельное окно (`chrome://extensions/content/...` или panel), для взаимодействия — `switch_to_window`
- Некоторые Marionette команды из Firefox-специфичных wire commands могут отсутствовать в TB — тестировать каждую
- `--marionette-port` в TB работает так же, дефолт 2828

## Что вне scope MVP

- Проксирование мультипользовательских сессий (одна MCP session = один TB процесс)
- Управление удалённым TB через сеть (только localhost)
- Wire protocol версионирование (пишем под текущий TB 140+)
- GUI дистрибутив (только CLI/library)

## Референсы

- Marionette Protocol: https://firefox-source-docs.mozilla.org/testing/marionette/Protocol.html
- marionette_driver: https://firefox-source-docs.mozilla.org/testing/marionette/PythonTests.html
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Прецедент (Thunderbird-side WebExt MCP): https://github.com/TKasperczyk/thunderbird-mcp (наш проект дополняет его: они дают data access, мы даём UI automation)
- HuNote (проект-заказчик, будет первым consumer'ом): `~/@Projects/@Hubbitus/@public/HuNote`

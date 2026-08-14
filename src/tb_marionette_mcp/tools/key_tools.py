"""send_keys and hotkey parser (W3C keys)."""

from __future__ import annotations

from typing import Any, cast

from marionette_driver.keys import Keys
from marionette_driver.marionette import Marionette, WebElement

from tb_marionette_mcp.errors import InvalidArgumentError
from tb_marionette_mcp.session import MarionetteSession

_MOD_MAP = {
    "ctrl": cast(str, Keys.CONTROL),
    "control": cast(str, Keys.CONTROL),
    "shift": cast(str, Keys.SHIFT),
    "alt": cast(str, Keys.ALT),
    "meta": cast(str, Keys.META),
    "cmd": cast(str, Keys.META),
    "command": cast(str, Keys.META),
}

_NAMED = {
    "enter": cast(str, Keys.ENTER),
    "return": cast(str, Keys.RETURN),
    "escape": cast(str, Keys.ESCAPE),
    "esc": cast(str, Keys.ESCAPE),
    "tab": cast(str, Keys.TAB),
    "space": cast(str, Keys.SPACE),
    "delete": cast(str, Keys.DELETE),
    "backspace": cast(str, Keys.BACK_SPACE),
    "up": cast(str, Keys.ARROW_UP),
    "down": cast(str, Keys.ARROW_DOWN),
    "left": cast(str, Keys.ARROW_LEFT),
    "right": cast(str, Keys.ARROW_RIGHT),
    "home": cast(str, Keys.HOME),
    "end": cast(str, Keys.END),
    "pageup": cast(str, Keys.PAGE_UP),
    "pagedown": cast(str, Keys.PAGE_DOWN),
    "insert": cast(str, Keys.INSERT),
}

_FKEYS = {
    f"f{i}": cast(str, getattr(Keys, f"F{i}"))
    for i in range(1, 13)
}


def parse_chord(chord: str) -> tuple[list[str], str]:
    tokens = [t.strip() for t in chord.replace(" ", "+").split("+") if t.strip()]
    if not tokens:
        raise InvalidArgumentError("empty chord")
    mods: list[str] = []
    for tok in tokens[:-1]:
        code = _MOD_MAP.get(tok.lower())
        if code is None:
            raise InvalidArgumentError(f"unknown modifier: {tok!r}")
        mods.append(code)
    key_tok = tokens[-1]
    lower = key_tok.lower()
    if lower in _NAMED:
        return mods, _NAMED[lower]
    if lower in _FKEYS:
        return mods, _FKEYS[lower]
    if len(key_tok) == 1:
        return mods, key_tok.lower()
    raise InvalidArgumentError(f"unknown key: {key_tok!r}")


def _element(client: Marionette, element_id: str) -> WebElement:
    return WebElement(client, element_id)


async def send_keys(
    keys: str, element_id: str | None = None
) -> dict[str, Any]:
    session = MarionetteSession.get()

    def _send() -> None:
        if element_id is not None:
            _element(session.client, element_id).send_keys(keys)
        else:
            actions = session.client.actions.key_action()
            for ch in keys:
                actions = actions.key_down(ch).key_up(ch)
            actions.perform()

    await session.call(_send)
    return {}


async def send_hotkey(
    chord: str, element_id: str | None = None
) -> dict[str, Any]:
    mods, key = parse_chord(chord)
    session = MarionetteSession.get()

    def _send() -> None:
        actions = session.client.actions.key_action()
        for m in mods:
            actions = actions.key_down(m)
        actions = actions.key_down(key).key_up(key)
        for m in reversed(mods):
            actions = actions.key_up(m)
        actions.perform()

    await session.call(_send)
    return {}

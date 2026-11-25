"""docs/modbus-map.md must match the register map in code."""

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "render_modbus_map.py"


def _load():
    spec = importlib.util.spec_from_file_location("render_modbus_map", _PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_doc_is_up_to_date():
    mod = _load()
    assert mod.main(["--check"]) == 0, "Run `make modbus-map` and commit docs/modbus-map.md"


def test_every_register_key_appears_in_the_doc():
    mod = _load()
    text = mod.DOC.read_text()
    from app.modbus.registers import REGISTERS

    assert [r.key for r in REGISTERS if f"`{r.key}`" not in text] == []

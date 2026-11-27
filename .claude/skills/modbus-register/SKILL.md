---
name: modbus-register
description: Add or change a heat pump Modbus register, fault code or decode rule. Use when reading a new register, exposing one to Home Assistant, or correcting the map after a probe.
---

# Add or change a register

1. **Find the evidence.** Check `docs/modbus-map.md` (Sources) and anything in `incoming/`. Note whether the entry is in the vendor table, used by a community project, or observed on this pump.
2. **Edit the code, not the doc tables.** Registers live in `app/modbus/registers.py`, faults in `app/modbus/faults.py`. Set the table, address, codec, unit, raw range and step, evidence and notes.
3. **Leave `app_writable` false.** Making a point writable by the app needs an approved OpenSpec change and a deliberate change to the pinned allowlist in `tests/unit/test_registers.py`. Never make forced defrost, factory reset or a service parameter writable.
4. **Respect the bus rules.** Reads use fixed blocks from allowed first addresses. If the register sits in a block the vendor does not label as a first address, record that in the notes and in the verification table.
5. **Add tests**: a decode case in `tests/unit/test_codec.py`, and a block-start case in `tests/unit/test_registers.py` for a register in a new block.
6. **Re-render the doc**: `make modbus-map`. Update the prose in `docs/modbus-map.md` if a reserved range or an open question changed.
7. Run `make check`.

---
name: live-probe
description: Talk to the real heat pump or its Modbus gateway, for example to verify the register map or investigate a reading. Use before running anything that opens a connection to the pump.
---

# Live probe

The pump is real hardware. A probe is read-only unless the user says otherwise in this session.

1. **Ask first.** Tell the user exactly which reads you will issue and wait for a go-ahead. Permission from an earlier session does not carry over.
2. **Check the bus is free.** The stock WiFi module must be unplugged, and the controller container must be stopped (`make down`), because the pump allows one master and the gateway should have one client.
3. **Use the probe.** Run `uv run python -m app.modbus.probe <host> --output <file>` (see `README.md`). It reads only, with function codes 01, 02, 03 and 04, in vendor shapes (48 bits or 3 registers, 60 ms apart). Add `--extended` to also read holding block 24 and input blocks 15, 18, 21, 24, 27 and 30, which are outside the vendor's allowed first addresses and reported as unverified; this is the one exception to the allowed-first-address rule and applies to the probe only. Do not write ad-hoc Modbus code instead.
4. **Never write** (function codes 05, 06, 15, 16) during a probe. If a write test is needed, it must be on the app allowlist, agreed with the user for that specific register and value, and followed by a read-back.
5. **Stop on trouble.** The probe handles this itself. A refused block (a Modbus exception such as 0x02) is an answer from the pump: it is recorded and the run continues. Two failed blocks in a row (no reply, gateway exception 0x0A or 0x0B, wrong length) end the run, and so does a lost connection. Never retry in a loop, and report what the transcript shows.
6. **Record the result.** Save the raw transcript under `.agents/` and fill in the verification table in `docs/modbus-map.md` with the date. Ask the user to read the matching values off the pump's display for comparison.
7. If the map was wrong, fix it with the `modbus-register` skill.

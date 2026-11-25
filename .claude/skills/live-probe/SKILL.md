---
name: live-probe
description: Talk to the real heat pump or its Modbus gateway, for example to verify the register map or investigate a reading. Use before running anything that opens a connection to the pump.
---

# Live probe

The pump is real hardware. A probe is read-only unless the user says otherwise in this session.

1. **Ask first.** Tell the user exactly which reads you will issue and wait for a go-ahead. Permission from an earlier session does not carry over.
2. **Check the bus is free.** The stock WiFi module must be unplugged, and the controller container must be stopped (`make down`), because the pump allows one master and the gateway should have one client.
3. **Read only, in vendor shapes.** Function codes 01, 02, 03 and 04 only. Counts of 48 for bit tables and 3 for register tables, from the first addresses listed in `docs/modbus-map.md`. Wait at least 60 ms between requests.
4. **Never write** (function codes 05, 06, 15, 16) during a probe. If a write test is needed, it must be on the app allowlist, agreed with the user for that specific register and value, and followed by a read-back.
5. **Stop on trouble.** If the pump stops answering or returns exception codes, stop, do not retry in a loop, and report what was sent.
6. **Record the result.** Save the raw transcript under `.agents/` and fill in the verification table in `docs/modbus-map.md` with the date. Ask the user to read the matching values off the pump's display for comparison.
7. If the map was wrong, fix it with the `modbus-register` skill.

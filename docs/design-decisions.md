# Design decisions

Decisions made so far, with the reason for each. Add to this file when a spec settles something; do not reverse an entry without asking the user.

## Decided

- **Local Modbus, not Tuya.** The stock WiFi module is a Tuya device that needs a cloud-issued key. The pump's RS485 header gives full local access with no account. The WiFi module is unplugged and the phone app is given up.
- **Modbus TCP through a Waveshare RS485-to-Ethernet gateway**, in Modbus TCP to RTU mode. The user already owns one, and a community project runs a Fairland IPHCR45 this way.
- **Standalone Docker service with MQTT discovery**, not a Home Assistant custom component. Same shape as the user's `gw-charger-controller`.
- **The register map is code.** `app/modbus/registers.py` is the single source of truth; the doc tables are rendered from it and checked in CI.
- **Narrow write allowlist.** Power, operating mode, power mode and setpoints only. Service parameters can damage the unit if set badly, so they stay read-only even though the pump accepts writes.
- **Vendor read shapes are mandatory.** The vendor says other shapes may return incorrect data, so the client reads fixed blocks and never single registers.
- **Read-only until verified.** No writes to the pump until the verification table in `docs/modbus-map.md` is complete for the AXCR21V.

## Open questions

- Which control board the AXCR21V has, and whether it follows the MWH216 / MWH298 map at all.
- Whether the gateway is powered from the header's 12 V or separately. The WiFi module draws little; the gateway's draw must be checked first.
- Whether holding register 25 and input registers 15–31 can be read (they fall outside the vendor's labelled first addresses).
- Whether the app should reassert the chosen power mode after a power cycle (one owner reports the unit falling back to silence).
- Whether forced defrost should ever be exposed as a Home Assistant button.
- Whether to expose a single climate entity, separate entities per setpoint, or both.

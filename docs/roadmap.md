# Roadmap

Planned changes, in order. Each becomes an OpenSpec change (`openspec/changes/<name>/`) when it is picked up, and is archived into `openspec/specs/` when done. See `docs/ways-of-working.md`.

| # | Change name | Purpose | Status |
|---|---|---|---|
| 001 | `readonly-probe` | A read-only command-line probe that reads every block through the gateway and prints raw and decoded values, to verify the map on the AXCR21V | done (archived; PR open) |
| 002 | `modbus-client` | Async client: fixed block reads, request spacing, allowlisted writes with read-back, reconnect and backoff | planned |
| 003 | `config-and-state` | Config loading and validation, `AppState`, debounced persistence of settings to `config.yaml` | planned |
| 004 | `poll-loop` | Poll loop, immutable snapshots, command queue | planned |
| 005 | `mqtt-discovery-sensors` | MQTT client, device and discovery payloads, read-only sensors and fault reporting | planned |
| 006 | `mqtt-controls` | Power, operating mode, power mode and setpoint control from Home Assistant; climate entity | planned |
| 007 | `diagnostics` | Diagnostic entities: connection state, error counters, last-poll age, firmware and model, app version | planned |

Spec 001 comes first because every later change depends on knowing the map is right for this pump.

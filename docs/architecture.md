# Architecture

Only `app/modbus/registers.py`, `codec.py`, `faults.py` and the read-only probe exist today. The rest is the intended shape, to be confirmed by each change's design.

```
Home Assistant  <--MQTT discovery/state/commands-->  app/ha/        MQTT client, entities, command parsing
                                                       |
                                                    app/state/     AppState (mutable), persisted fields
                                                       |
                                                    app/control/   poll loop, immutable snapshots
                                                       |
                                                    app/modbus/    register map, codec, faults, client
                                                       |  Modbus TCP
                                                 RS485 gateway  --RS485 Modbus RTU-->  heat pump (unit 1)
```

- `app/modbus/`: the register map is data; the codec is pure; the client owns block reads, request spacing, reconnect and backoff. No other module builds a Modbus request.
- `app/control/`: polls the pump on an interval, applies queued commands, builds an immutable snapshot for publishing.
- `app/ha/`: MQTT discovery, state publishing, command validation. A command is validated (type, range, allowed values) before it touches state or the pump.
- `app/state/` and `app/config.py`: runtime state; settings changed from Home Assistant are persisted to `config.yaml` and exposed as entities.
- Diagnostics (connection state, error counts, last-poll age, raw fault codes, firmware and model) are published as diagnostic entities.

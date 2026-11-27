# Domain conventions

Units, signs and naming used across the app. Change them only through an OpenSpec change.

## Units and values

- **Temperatures** are in °C. Raw temperature registers are decoded by `app/modbus/codec.py`; no other code applies the formulas.
- **Setpoints** are whole degrees (raw step 2). Each operating mode has its own setpoint register; the active one follows the operating mode.
- **Compressor current** is in A (raw / 10). **PFC voltage** is in V.
- **Compressor power** is an estimate: `compressor_current × pfc_voltage`, in W. It is apparent power for the compressor only and must be labelled as estimated.
- **Compressor speed** is a percentage. **Compressor frequency** is in Hz. **Fan speed** is in RPM.

## Naming

- Register keys in `app/modbus/registers.py` are the canonical names. State fields, MQTT topics and entity ids reuse them.
- Operating mode means auto / heating / cooling (holding register 0). Power mode means smart / silence / super silence / turbo (holding register 1). Do not call either one just "mode".
- "Fault" covers both failures and protections. The fault table marks which is which.

## Modbus

- Addresses are zero-based protocol addresses, as written in the vendor table.
- The pump is unit id 1. The gateway speaks Modbus TCP to the app and RTU to the pump.
- Bus rules and the write policy are in `docs/modbus-map.md`.

## Site

- Timezone is Australia/Perth (UTC+8); `docker-compose.yml` sets `TZ`. Log and persist timestamps in UTC.

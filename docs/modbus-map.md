# Modbus map

The register map for Fairland pool heat pumps with an MWH216 or MWH298 control board. The project's reference unit is a TiLAB TurboSilence AXCR21V, a rebadged Fairland.

**Status: not yet verified on the AXCR21V.** Every entry comes from Fairland's protocol table for the MWH216 / MWH298 control boards or from community projects on other Fairland models. The first job on real hardware is a read-only probe (see [Verification](#verification-on-the-axcr21v)).

The tables between `GENERATED` markers are rendered from `app/modbus/registers.py` and `app/modbus/faults.py`. Edit the code, then run `make modbus-map`. A unit test fails if this file is stale.

## Transport

| Item | Value | Source |
|---|---|---|
| Physical layer | RS485, Modbus RTU | vendor |
| Serial format | 9600 baud, 8 data bits, no parity, 1 stop bit | vendor (parity from community) |
| Unit (slave) id | 1 | vendor |
| Pump role | slave; exactly one master on the bus | vendor |
| Connection point | 4-pin WiFi-module header on the control board, labelled `B A G +12V`, often repeated on an external cabinet socket | community |
| Gateway | Waveshare RS485-to-Ethernet in **Modbus TCP to RTU** mode; the app speaks Modbus TCP to it | project decision |
| Gateway TCP port | 4196 (Waveshare default) | community |

The stock WiFi module is itself a Modbus master. It must be unplugged while the gateway is connected.

## Bus rules

These come from the vendor protocol notes and are binding on all code that talks to the pump.

1. **Fixed read shapes.** A read must start on an allowed first address and request a fixed count. Any other shape "may return incorrect data". The allowed shapes are in the table below the rules.
2. **Request spacing.** Leave at least 60 ms between two requests.
3. **Writes are single-point.** Function 05 for a coil, function 06 for a holding register.

<!-- BEGIN GENERATED: read_blocks -->
| Table | Read function | Count | Allowed first addresses (vendor) |
|---|---|---:|---|
| coil | 01 | 48 | 0 |
| discrete_input | 02 | 48 | 0, 48 |
| holding | 03 | 3 | 0, 3, 6, 9, 12, 15, 18 |
| input | 04 | 3 | 0, 3, 6, 9, 12 |
<!-- END GENERATED: read_blocks -->

**Exception for the probe (decided 2026-11-26).** The read-only probe (`readonly-probe`) may read these extended blocks, with the vendor's fixed counts, when run with its extended flag: holding block 24, and input blocks 15, 18, 21, 24, 27 and 30. Values read this way are unverified. No other code may start a read off the allowed first addresses.

`Register.block_start` gives the block that contains a register. Two cases fall outside the vendor's labelled first addresses and need the probe to settle them: holding register 25 (block 24) and input registers 15–20 (blocks 15 and 18, read successfully by a community project on InverX units).

## Decoding

| Decode | Formula | Example |
|---|---|---|
| temp type 1 | °C = (raw − 60) / 2; raw = °C × 2 + 60 | raw 120 → 30 °C |
| temp type 2 | °C = raw / 2 | raw 120 → 60 °C |
| raw / 10 | value = raw / 10 | raw 53 → 5.3 A |

Setpoints have a raw step of 2, which is 1 °C.

There is no power register. Compressor power is estimated as `compressor_current × pfc_voltage`.

## Write policy

The **Write** column has three values:

- **app**: the app may write it. This is the complete allowlist: power, operating mode, power mode and the three setpoints.
- **device only**: the pump accepts writes, but the app must never issue one. This covers forced defrost, factory reset, and the pump, defrost and expansion-valve service parameters.
- **—**: read-only on the pump.

Moving a register to **app** needs an approved OpenSpec change. `app/modbus/codec.py` refuses to encode a value for anything else, and a unit test pins the allowlist.

## Coils (read 01, write 05)

<!-- BEGIN GENERATED: coil -->
| Addr | Key | Name | Decode | Unit | Raw range (decoded) | Write | Evidence | Notes |
|---:|---|---|---|---|---|---|---|---|
| 0 | `power` | Power switch | bit |  |  | app | vendor+field |  |
| 1 | `forced_defrost` | Compulsory defrosting | bit |  |  | device only | vendor | Write 1 to enter. Not written by the app. |
| 2 | `factory_reset` | Restore factory values | bit |  |  | device only | vendor | Marked reserved by the vendor. Never write. |
<!-- END GENERATED: coil -->

Addresses 3–47 are reserved.

## Discrete inputs (read 02)

<!-- BEGIN GENERATED: discrete_input -->
| Addr | Key | Name | Decode | Unit | Raw range (decoded) | Write | Evidence | Notes |
|---:|---|---|---|---|---|---|---|---|
| 0 | `running` | On/off state | bit |  |  | — | vendor+field |  |
| 1 | `defrosting` | Defrosting | bit |  |  | — | vendor |  |
| 2 | `din1` | Digital input DIN1 | bit |  |  | — | vendor | Function unverified. |
| 3 | `din2` | Digital input DIN2 | bit |  |  | — | vendor | Function unverified. |
| 4 | `din3` | Digital input DIN3 | bit |  |  | — | vendor | Function unverified. |
| 5 | `din4` | Digital input DIN4 | bit |  |  | — | vendor | Function unverified. |
| 6 | `din5` | Digital input DIN5 | bit |  |  | — | vendor | Function unverified. |
| 7 | `out1` | Output OUT1 | bit |  |  | — | vendor | Function unverified. |
| 8 | `out2` | Output OUT2 | bit |  |  | — | vendor | Function unverified. |
| 9 | `out3` | Output OUT3 | bit |  |  | — | vendor | Function unverified. |
| 10 | `out4` | Output OUT4 | bit |  |  | — | vendor | Function unverified. |
| 11 | `out5` | Output OUT5 | bit |  |  | — | vendor | Function unverified. |
| 12 | `out6` | Output OUT6 | bit |  |  | — | vendor | Function unverified. |
| 13 | `out7` | Output OUT7 | bit |  |  | — | vendor | Function unverified. |
| 14 | `out8` | Output OUT8 | bit |  |  | — | vendor | Function unverified. |
| 15 | `out9` | Output OUT9 | bit |  |  | — | vendor | Function unverified. |
| 16 | `fault_indicator` | Malfunction / protection indicator | bit |  |  | — | vendor+field | Some boards leave this at 0; combine with the fault block (48-95). |
| 17 | `compressor_demand` | Compressor running demand | bit |  |  | — | vendor |  |
<!-- END GENERATED: discrete_input -->

Addresses 18–47 are reserved. An older revision of the protocol table, quoted in a community project, names inputs 2–17 differently (for example 7 water flow switch, 8 high pressure switch, 9 low pressure switch, 10 compressor, 11 fan, 12 four-way valve, 17 circulation pump). Treat the DIN/OUT functions as unknown until probed.

## Fault block (discrete inputs 48–95)

Read as one block of 48 starting at address 48. Addresses not listed are reserved; a set bit there is reported as an unknown fault.

<!-- BEGIN GENERATED: faults -->
| Addr | Code | Kind | Description |
|---:|---|---|---|
| 48 | E0 | failure | Unknown code E0 |
| 49 | E1 | failure | High pressure protection |
| 50 | E2 | failure | Low pressure protection |
| 51 | E3 | protection | No water flow |
| 52 | E4 | failure | 3-phase sequence protection (three-phase units only) |
| 53 | E5 | protection | Power supply outside operating range |
| 54 | E6 | protection | Insufficient water flow, excessive inlet/outlet temperature difference |
| 55 | E7 | failure | Water outlet temperature too high or too low |
| 56 | E8 | failure | High exhaust temperature protection |
| 57 | E9 | failure | Unknown code E9 |
| 58 | EA | failure | Evaporator overheat protection (cooling mode) |
| 59 | Eb | protection | Ambient temperature too high or too low |
| 61 | Ed | protection | Anti-freezing reminder |
| 64 | P0 | failure | Controller communication failure |
| 65 | P1 | failure | Water inlet temperature sensor failure |
| 66 | P2 | failure | Water outlet temperature sensor failure |
| 67 | P3 | failure | Gas exhaust temperature sensor failure |
| 68 | P4 | failure | Evaporator coil temperature sensor failure |
| 69 | P5 | failure | Gas return temperature sensor failure |
| 70 | P6 | failure | Cooling coil temperature sensor failure |
| 71 | P7 | failure | Ambient temperature sensor failure |
| 72 | P8 | failure | Cooling plate sensor failure |
| 73 | P9 | failure | Current sensor failure |
| 74 | PA | failure | Restart memory failure |
| 80 | F0 | failure | Unknown code F0 |
| 81 | F1 | failure | Compressor drive module failure |
| 82 | F2 | failure | PFC module failure |
| 83 | F3 | failure | Compressor start failure |
| 84 | F4 | failure | Compressor running failure |
| 85 | F5 | failure | Inverter board over-current protection |
| 86 | F6 | failure | Inverter board overheat protection |
| 87 | F7 | failure | Current protection |
| 88 | F8 | failure | Cooling plate overheat protection |
| 89 | F9 | failure | Fan motor failure |
| 90 | FA | failure | PFC module over-current protection |
| 91 | Fb | failure | Power filter board no-power protection |
<!-- END GENERATED: faults -->

## Holding registers (read 03, write 06)

<!-- BEGIN GENERATED: holding -->
| Addr | Key | Name | Decode | Unit | Raw range (decoded) | Write | Evidence | Notes |
|---:|---|---|---|---|---|---|---|---|
| 0 | `operating_mode` | Function selection | raw |  | 0–2 | app | vendor+field | 0 auto, 1 heating, 2 cooling. |
| 1 | `power_mode` | Working mode selection | raw |  | 0–3 | app | vendor+field | 0 smart, 1 silence, 2 super silence (community), 3 turbo (not on all models). |
| 2 | `target_temp_auto` | Auto mode target temperature | temp type 1 | °C | 84–140 (12–40), step 2 | app | vendor+field |  |
| 3 | `target_temp_heating` | Heating mode target temperature | temp type 1 | °C | 96–140 (18–40), step 2 | app | vendor+field |  |
| 4 | `target_temp_cooling` | Cooling mode target temperature | temp type 1 | °C | 84–120 (12–30), step 2 | app | vendor+field |  |
| 5 | `pump_mode` | Water pump working mode (P0) | raw |  | 0–2 | device only | vendor | 0 continuous, 1 water temperature control, 2 time / water temperature control. |
| 6 | `pump_time` | Water pump working time (P1) | raw | min | 10–120, step 5 | device only | vendor |  |
| 7 | `defrost_interval` | Compressor run time before defrost | raw | min | 30–90 | device only | vendor |  |
| 8 | `defrost_entry_temp` | Defrost entry temperature (P3) | temp type 1 | °C | 26–60 (-17–0), step 2 | device only | vendor |  |
| 9 | `defrost_max_time` | Maximum defrost run time (P4) | raw | min | 1–12 | device only | vendor |  |
| 10 | `defrost_exit_temp` | Defrost exit temperature (P5) | temp type 1 | °C | 76–120 (8–30), step 2 | device only | vendor |  |
| 17 | `eev_superheat_heating` | Expansion valve superheat, heating | temp type 1 | °C | 40–100 (-10–20), step 2 | device only | vendor |  |
| 18 | `eev_superheat_cooling` | Expansion valve superheat, cooling | temp type 1 | °C | 40–100 (-10–20), step 2 | device only | vendor |  |
| 25 | `power_off_memory` | Power-off restart memory | raw |  | 0–1 | device only | vendor | 1 restores the pre-power-down state. |
<!-- END GENERATED: holding -->

Addresses 11–16, 19–24 and 26–32 are reserved in the vendor table. The older table revision lists 19–21 as expansion-valve manual mode and opening settings; they are not in this map and must not be written.

## Input registers (read 04)

<!-- BEGIN GENERATED: input -->
| Addr | Key | Name | Decode | Unit | Raw range (decoded) | Write | Evidence | Notes |
|---:|---|---|---|---|---|---|---|---|
| 0 | `compressor_speed_pct` | Compressor running speed | raw | % |  | — | vendor+field |  |
| 1 | `compressor_target_freq` | Compressor target frequency | raw | Hz |  | — | vendor |  |
| 2 | `pfc_voltage` | PFC voltage | raw | V |  | — | vendor+field |  |
| 3 | `inlet_temp` | Water inlet temperature (AIN1) | temp type 1 | °C |  | — | vendor+field |  |
| 4 | `outlet_temp` | Water outlet temperature (AIN2) | temp type 1 | °C |  | — | vendor+field |  |
| 5 | `ambient_temp` | Ambient temperature (AIN7) | temp type 1 | °C |  | — | vendor+field |  |
| 6 | `exhaust_temp` | Gas exhaust temperature (AIN5) | temp type 2 | °C |  | — | vendor |  |
| 7 | `evaporator_coil_temp` | Outer coil temperature, evaporator (AIN3) | temp type 1 | °C |  | — | vendor |  |
| 8 | `suction_temp` | Gas return temperature (AIN6) | temp type 1 | °C |  | — | vendor |  |
| 9 | `exchanger_coil_temp` | Inner coil temperature, heat exchanger (AIN4) | temp type 1 | °C |  | — | vendor+field |  |
| 10 | `compressor_freq` | Compressor frequency | raw | Hz |  | — | vendor+field |  |
| 11 | `compressor_current` | Compressor current | raw / 10 | A |  | — | vendor+field |  |
| 12 | `cooling_plate_temp` | Cooling plate temperature | temp type 2 | °C |  | — | vendor |  |
| 13 | `eev_opening` | Expansion valve opening | raw |  |  | — | vendor |  |
| 14 | `fan_speed` | DC fan motor speed | raw | RPM |  | — | vendor |  |
| 15 | `auto_temp_min` | Auto setpoint lower limit | temp type 1 | °C |  | — | community | InverX only; reads 0 where unsupported. |
| 16 | `auto_temp_max` | Auto setpoint upper limit | temp type 1 | °C |  | — | community | InverX only; reads 0 where unsupported. |
| 17 | `heating_temp_min` | Heating setpoint lower limit | temp type 1 | °C |  | — | community | InverX only; reads 0 where unsupported. |
| 18 | `heating_temp_max` | Heating setpoint upper limit | temp type 1 | °C |  | — | community | InverX only; reads 0 where unsupported. |
| 19 | `cooling_temp_min` | Cooling setpoint lower limit | temp type 1 | °C |  | — | community | InverX only; reads 0 where unsupported. |
| 20 | `cooling_temp_max` | Cooling setpoint upper limit | temp type 1 | °C |  | — | community | InverX only; reads 0 where unsupported. |
<!-- END GENERATED: input -->

Addresses 15–29 are reserved in the vendor table. The older table revision lists further registers that are not in this map yet: 21–25 board version (ASCII), 26–29 model code (ASCII), 30 supply voltage, 31 compressor restart delay in seconds. The probe should read them.

## Known behaviour from other models

- **Power mode may not persist.** One owner reports the unit often returns to silence at power-on.
- **Turbo (power mode 3)** did nothing on one IPS Pro unit. The vendor table says some models lack it.
- **Mode change after power-on.** One community implementation waits 5 s between switching the pump on and writing the mode register.
- **One unit never answered.** An owner with an MWH298-V2.1 board got no reply at all; the cause was never found.

## Verification on the AXCR21V

Fill this in from the first read-only probe. Until then no write may be issued to the pump.

| Check | Result | Date |
|---|---|---|
| Control board model and revision | | |
| Gateway reaches the pump (unit 1, 9600 8N1) | | |
| Fixed block reads return data for every allowed first address | | |
| Inlet, outlet and ambient temperatures match the display | | |
| Operating mode, power mode and setpoint match the display | | |
| Input registers 15–20 (setpoint limits) return non-zero values | | |
| Holding register 25 is readable (block 24) | | |
| Input registers 21–31 (version, model, supply voltage) | | |
| DIN/OUT functions identified | | |

## Sources

- Vendor protocol table for MWH216 / MWH298 boards, published as an image in [spdr870/fairland_iphcr45_modbus](https://github.com/spdr870/fairland_iphcr45_modbus) (`images/modbus_overview.jpg`). Model: IPHCR45, via a Waveshare RS485-to-Ethernet gateway.
- [King007t/esphome-fairland-heatpump](https://github.com/King007t/esphome-fairland-heatpump): InverX and Inverter Plus series; block reads, setpoint limits, fault descriptions.
- [rstcologne/ESP-Home-Fairland-Heatpump](https://github.com/rstcologne/ESP-Home-Fairland-Heatpump): IPS Pro; quotes an older revision of the vendor table.
- [Home Assistant community thread](https://community.home-assistant.io/t/controlling-a-fairland-pool-heatpump-eliminating-tuya/579467).
- Fairland brochure listing the AXCR21V: <https://www.fairland.com.cn/static/upload/file/20241010/1728545417300901.pdf>.

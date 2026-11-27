## Why

The register map in `docs/modbus-map.md` comes from Fairland's protocol table and from community projects on other models. It has never been checked against the reference unit, a TiLAB TurboSilence AXCR21V. Every later spec depends on that map being right, and the project's safety rules forbid any write to the pump until it is verified.

This spec delivers a command-line probe that connects to the pump through the RS485 gateway, reads the map once using only the vendor's read shapes, and reports the raw and decoded values so the maintainer can compare them with the pump's display and fill in the verification table.

The probe never writes to the pump. It is a one-shot diagnostic tool, not part of the running controller.

## What Changes

### In scope

- One-shot, read-only reads of every block in the map over Modbus TCP.
- A human-readable report and a machine-readable transcript.
- Opt-in reads of blocks the vendor does not label as allowed first addresses.

### Out of scope

- Any Modbus write.
- Continuous polling, MQTT, Home Assistant, and `config.yaml`.
- Automatically editing `docs/modbus-map.md`. The maintainer records the results.
- Auto-detecting serial settings or scanning for unit ids.

## Impact

### Deviation from bus rule 1

`AGENTS.md` safety rule 3 and bus rule 1 in `docs/modbus-map.md` say a read must start on a first address the vendor labels as allowed. The extended blocks in this spec do not. This is a deliberate, narrow exception:

- It applies to the probe only, never to the controller.
- It is opt-in per run, read-only, and uses the vendor's fixed counts.
- It covers exactly the blocks `docs/modbus-map.md` asks the probe to settle: holding register 25 (block 24) and input registers 15–20 "need the probe to settle them", and of input registers 21–31 it says "the probe should read them". `docs/design-decisions.md` lists the same point as an open question.

The maintainer agreed this exception explicitly on 2026-11-26, separately from approval of this document. The rule wording in `AGENTS.md`, `docs/modbus-map.md` and the documents that restate it was amended on this branch at the same time (see Constraint 5), so the binding documents and the spec agree.

The vendor's stated risk for an unlabelled read is that it "may return incorrect data". The report therefore labels every extended value as unverified.


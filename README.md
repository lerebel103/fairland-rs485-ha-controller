# Fairland RS485 HA Controller

A local bridge between Fairland-built pool heat pumps and Home Assistant. It reads and controls the pump over the RS485 Modbus port on its control board and publishes it to Home Assistant through MQTT discovery. No cloud and no Tuya account.

**Status: scaffold.** The register map, tooling and specs process are in place. The controller itself is not implemented yet; see the [roadmap](specs/README.md).

## How it connects

```
Home Assistant <--MQTT--> controller (Docker) <--Modbus TCP--> RS485 gateway <--RS485--> heat pump
```

Fairland control boards are Modbus RTU slaves on the 4-pin header the WiFi module plugs into. An RS485-to-Ethernet gateway takes the WiFi module's place.

## Supported heat pumps

Fairland builds pool heat pumps that are sold under its own name and under many other brands. This project targets the units that use Fairland's MWH216 or MWH298 control board and its published Modbus protocol.

| Model | Status |
|---|---|
| TiLAB TurboSilence AXCR21V | Reference unit. The project is designed for it; verification on the hardware is the first roadmap item |
| TiLAB TurboSilence AXCR series (AXCR13V to AXCR32V) | Expected to work; same range as the reference unit |
| Fairland InverX (IXR / IXCR) | Expected to work; community projects use the same register map |
| Fairland Inverter Plus (IPHCR, e.g. IPHCR45) | Expected to work; a community project runs one through the same kind of gateway |
| Pool Systems IPS Pro and other rebadged Fairland units | Expected to work where the board is an MWH216 or MWH298 |

"Expected to work" means the register map matches what other people have published for those models. It has not been tested by this project. If your unit has a WiFi module that pairs with a Fairland, Inverter Life or Smart Life app and a header labelled `B A G +12V`, it is a good candidate. Reports from other models are welcome.

## Hardware

- **Heat pump**: one of the models above.
- **Gateway**: an RS485-to-Ethernet gateway in Modbus TCP to RTU mode, serial 9600 8N1. The reference setup uses a Waveshare RS485 TO ETH.
- **Wiring**: the header is labelled `B A G +12V`. Connect A and B to the gateway and unplug the stock WiFi module, because the pump allows only one Modbus master.

Opening the unit exposes mains voltage and may affect the warranty.

## Register map

[docs/modbus-map.md](docs/modbus-map.md) holds the full map, the bus rules and the write policy. It is not yet verified on the reference unit.

## Quick start

Not usable yet. Once the controller is implemented:

```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your MQTT broker and gateway address
make up
```

## Development

```bash
uv sync --group dev
make check
```

`make help` lists the other targets. CI runs the same checks on every push; Docker images are built by GitHub Actions and need the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository secrets.

## Working with agents

The project is spec-driven and set up for Claude Code. Other agent tools can read `AGENTS.md`.

- [AGENTS.md](AGENTS.md): git policy, heat pump safety rules, architecture. `CLAUDE.md` imports it.
- [specs/](specs/README.md): the spec process and roadmap.
- [docs/ways-of-working.md](docs/ways-of-working.md): review loops, roles, severities, definition of done and the GitHub settings to apply.
- [docs/](docs/): `modbus-map.md`, `domain-conventions.md`, `design-decisions.md`, `dev-workflow.md`.
- `.claude/skills/`: `spec`, `review-loop`, `open-pr`, `pr-feedback`, `modbus-register`, `live-probe`, `release`.
- `.claude/agents/`: read-only reviewer subagents `spec-reviewer`, `code-reviewer`, `safety-reviewer`.
- `.github/`: PR template, review instructions for GitHub Copilot, and a branch ruleset for `main`.
- `.claude/settings.json`: shared permissions and a hook that blocks commits and pushes on `main`.
- Worktrees live under `.claude/worktrees/` (`make worktree name=<topic>`).

## License

MIT

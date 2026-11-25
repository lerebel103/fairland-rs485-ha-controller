"""Entry point for the Fairland RS485 HA controller."""

import argparse
import logging

from app.version import __version__

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and run the controller.

    Scaffold only: the controller itself is delivered by the specs in `specs/`.
    """
    parser = argparse.ArgumentParser(prog="app", description="Fairland RS485 HA controller")
    parser.add_argument("--config", default="config.yaml", help="path to the YAML config file")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("Fairland RS485 HA controller %s (config: %s)", __version__, args.config)
    logger.error("The controller is not implemented yet; see specs/README.md for the roadmap.")
    return 1

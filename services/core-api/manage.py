#!/usr/bin/env python
"""Django command-line utility for administrative tasks."""

import os
import sys


def main() -> None:
    environment = os.environ.get("ENVIRONMENT", "local")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"config.settings.{environment}")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - defensive
        raise ImportError(
            "Django is not installed. Run `uv sync` in services/core-api first."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

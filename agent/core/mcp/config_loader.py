"""Load MCP server definitions in a way that is independent of process CWD."""

import json
import sys
from pathlib import Path
from typing import Any


def load_mcp_servers_config(config_path: str | Path) -> dict[str, Any]:
    """Load MCP connections and normalize stdio process settings.

    ``subprocess`` resolves a relative ``cwd`` against the application's current
    working directory.  That changes between ``python -m agent.main``, test runs,
    and the web service.  Resolve it against the JSON file instead so the MCP
    server always starts from the intended directory.
    """
    resolved_config_path = Path(config_path).resolve()
    with resolved_config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    connections: dict[str, Any] = {}
    for name, definition in config.get("mcpServers", {}).items():
        connection = dict(definition)
        if connection.get("transport") == "stdio":
            configured_cwd = connection.get("cwd")
            if configured_cwd:
                cwd = Path(configured_cwd)
                if not cwd.is_absolute():
                    cwd = resolved_config_path.parent / cwd
                cwd = cwd.resolve()
                if not cwd.is_dir():
                    raise NotADirectoryError(
                        f"MCP server '{name}' has an invalid working directory: {cwd}"
                    )
                connection["cwd"] = str(cwd)

            # The server must use the same interpreter as this application;
            # otherwise a virtual environment may be bypassed on Windows.
            if connection.get("command") == "python":
                connection["command"] = sys.executable

        connections[name] = connection

    return connections

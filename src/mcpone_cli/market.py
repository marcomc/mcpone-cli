from __future__ import annotations

import json
import re
from pathlib import Path

from .models import JsonDict, MarketConnection, MarketTool

PLACEHOLDER_PATTERN = re.compile(r"<([A-Z0-9_]+)>")


def load_market_catalog(resources_dir: Path) -> list[MarketTool]:
    tools: list[MarketTool] = []
    for path in sorted(resources_dir.glob("[0-9][0-9][0-9]_*.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            tools.append(
                MarketTool(
                    category=str(item.get("category", path.stem)),
                    catalog_id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    author=item.get("author"),
                    explanation=item.get("explanation"),
                    version=item.get("version"),
                    github_url=item.get("githubUrl"),
                    package_url=item.get("packageUrl"),
                    github_star=item.get("githubStar"),
                    connections=[
                        MarketConnection(
                            type=str(connection.get("type", "STDIO")),
                            command=connection.get("command"),
                            args=list(connection.get("args", [])),
                            url=connection.get("url"),
                            headers=dict(connection.get("headers", {})),
                            parameters=dict(connection.get("parameters", {})),
                        )
                        for connection in item.get("connections", [])
                        if isinstance(connection, dict)
                    ],
                )
            )
    return tools


def find_market_tool(tools: list[MarketTool], ref: str) -> MarketTool:
    needle = ref.casefold()
    for tool in tools:
        if tool.name.casefold() == needle or tool.catalog_id.casefold() == needle:
            return tool
    raise KeyError(f"Market tool not found: {ref}")


def choose_connection(
    tool: MarketTool,
    preferred: str | None = None,
    provided_keys: set[str] | None = None,
) -> MarketConnection:
    provided = provided_keys or set()
    if preferred:
        candidates = [
            connection
            for connection in tool.connections
            if connection.type.casefold() == preferred.casefold()
        ]
        if not candidates:
            raise KeyError(f"Connection type not found: {preferred}")
        if provided:
            matching = [
                connection
                for connection in candidates
                if provided.issubset(set(connection.parameters.keys()))
            ]
            if matching:
                candidates = matching

        return max(
            candidates,
            key=lambda connection: (
                len(set(connection.parameters.keys()) & provided),
                len(connection.parameters),
                bool(connection.command),
                len(connection.args),
                len(connection.headers),
            ),
        )

    for wanted in ("STDIO", "STREAMABLE_HTTP"):
        for connection in tool.connections:
            if connection.type == wanted:
                return connection

    if not tool.connections:
        raise KeyError(f"Market tool has no connections: {tool.name}")
    return tool.connections[0]


def _normalize_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _replace_inline(template: str, values: JsonDict) -> str:
    def replacer(match: re.Match[str]) -> str:
        key = match.group(1)
        value = values.get(key)
        return "" if value is None else str(value)

    return PLACEHOLDER_PATTERN.sub(replacer, template)


def materialize_connection(
    tool: MarketTool,
    connection: MarketConnection,
    provided: JsonDict,
    version: str | None = None,
) -> dict[str, object]:
    values: JsonDict = {"VERSION": version or tool.version or "latest"}
    values.update(provided)

    args: list[str] = []
    consumed_keys: set[str] = set()
    for raw_arg in connection.args:
        match = PLACEHOLDER_PATTERN.fullmatch(raw_arg)
        if not match:
            args.append(_replace_inline(raw_arg, values))
            continue

        key = match.group(1)
        consumed_keys.add(key)
        meta = connection.parameters.get(key, {})
        value = values.get(key, meta.get("default"))
        if value in (None, ""):
            if meta.get("required"):
                raise ValueError(f"Missing required market parameter: {key}")
            continue

        if str(meta.get("type", "")).lower() == "boolean":
            if _normalize_bool(value):
                if meta.get("flag"):
                    args.append(str(meta["flag"]))
                elif meta.get("prefix"):
                    args.extend([str(meta["prefix"]), "true"])
            continue

        if meta.get("prefix"):
            args.extend([str(meta["prefix"]), str(value)])
        elif meta.get("flag"):
            args.extend([str(meta["flag"]), str(value)])
        else:
            args.append(str(value))

    for key, meta in connection.parameters.items():
        if key in consumed_keys:
            continue
        value = values.get(key, meta.get("default"))
        if value in (None, ""):
            if meta.get("required"):
                raise ValueError(f"Missing required market parameter: {key}")
            continue

        if str(meta.get("type", "")).lower() == "boolean":
            if _normalize_bool(value):
                if meta.get("flag"):
                    args.append(str(meta["flag"]))
                elif meta.get("prefix"):
                    args.extend([str(meta["prefix"]), "true"])
            continue

        if meta.get("prefix"):
            args.extend([str(meta["prefix"]), str(value)])
        elif meta.get("flag"):
            args.extend([str(meta["flag"]), str(value)])

    headers = {
        key: _replace_inline(str(value), values)
        for key, value in connection.headers.items()
        if _replace_inline(str(value), values)
    }

    return {
        "name": tool.name,
        "source": "market",
        "server_type": connection.type,
        "command": connection.command,
        "args": args,
        "url": _replace_inline(connection.url, values) if connection.url else None,
        "headers": headers,
        "parameters": connection.parameters,
        "version": version or tool.version or "latest",
    }

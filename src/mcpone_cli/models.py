from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JsonDict = dict[str, Any]


@dataclass(slots=True)
class AddedApp:
    pk: int
    name: str
    app_id: str
    ai_agent_id: str | None
    active_cluster_id: str | None
    config_path: str | None
    config_key: str | None
    project_path: str | None
    explanation: str | None


@dataclass(slots=True)
class Cluster:
    pk: int
    app_pk: int
    name: str
    cluster_id: str
    enabled_server_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AddedServer:
    pk: int
    server_id: str
    name: str
    source: str
    server_type: str
    command: str | None
    url: str | None
    version: str | None
    args: list[str] = field(default_factory=list)
    env: JsonDict = field(default_factory=dict)
    headers: JsonDict = field(default_factory=dict)
    parameters: JsonDict = field(default_factory=dict)
    custom_fields: JsonDict = field(default_factory=dict)


@dataclass(slots=True)
class MarketConnection:
    type: str
    command: str | None
    args: list[str]
    url: str | None
    headers: JsonDict
    parameters: JsonDict


@dataclass(slots=True)
class MarketTool:
    category: str
    catalog_id: str
    name: str
    author: str | None
    explanation: str | None
    version: str | None
    github_url: str | None
    package_url: str | None
    github_star: int | None
    connections: list[MarketConnection] = field(default_factory=list)

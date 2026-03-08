from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import load_settings
from .formats import (
    enabled_servers_to_config,
    load_config_map,
    parse_server_key,
    server_to_config_dict,
    write_config_map,
)
from .market import choose_connection, find_market_tool, load_market_catalog, materialize_connection
from .store import McpOneStore, generate_server_id

console = Console()
app = typer.Typer(
    help="Manage McpOne apps, clusters, servers, market tools, and config sync.",
    invoke_without_command=True,
    no_args_is_help=True,
)
apps_app = typer.Typer(help="Manage McpOne apps.")
clusters_app = typer.Typer(help="Manage McpOne clusters.")
servers_app = typer.Typer(help="Manage McpOne servers.")
market_app = typer.Typer(help="Inspect and install market tools.")
sync_app = typer.Typer(help="Sync McpOne state to agent config files.")
import_app = typer.Typer(help="Import agent config files into McpOne.")

app.add_typer(apps_app, name="apps")
app.add_typer(clusters_app, name="clusters")
app.add_typer(servers_app, name="servers")
app.add_typer(market_app, name="market")
app.add_typer(sync_app, name="sync")
app.add_typer(import_app, name="import")


@dataclass(slots=True)
class Runtime:
    store: McpOneStore
    resources_dir: Path
    backup_on_write: bool


def _state(ctx: typer.Context) -> Runtime:
    return ctx.obj


def _parse_pairs(items: list[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise typer.BadParameter(f"Expected KEY=VALUE, got: {item}")
        key, value = item.split("=", 1)
        output[key] = value
    return output


def _backup_if_needed(runtime: Runtime) -> None:
    if runtime.backup_on_write and runtime.store.db_path.exists():
        backup_path = runtime.store.backup()
        console.print(f"[dim]DB backup:[/dim] {backup_path}")


def _version_callback(value: bool) -> None:
    if value:
        console.print(__version__)
        raise typer.Exit()


def _parse_target(raw: str) -> tuple[str, str]:
    for separator in ("::", "/"):
        if separator in raw:
            app_name, cluster_name = raw.split(separator, 1)
            if app_name.strip() and cluster_name.strip():
                return app_name.strip(), cluster_name.strip()
    raise typer.BadParameter(f"Expected target in the form APP::CLUSTER or APP/CLUSTER, got: {raw}")


@app.callback()
def main_callback(
    ctx: typer.Context,
    config: Path | None = typer.Option(None, "--config", help="Optional config.toml path."),
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the mcpone-cli version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
):
    del version
    settings = load_settings(config)
    ctx.obj = Runtime(
        store=McpOneStore(settings.db_path),
        resources_dir=settings.resources_dir,
        backup_on_write=settings.backup_on_write,
    )


@apps_app.command("list")
def apps_list(ctx: typer.Context):
    runtime = _state(ctx)
    table = Table("Name", "App ID", "Agent", "Active Cluster", "Config")
    for item in runtime.store.list_apps():
        table.add_row(
            item.name,
            item.app_id,
            item.ai_agent_id or "",
            item.active_cluster_id or "",
            item.config_path or "",
        )
    console.print(table)


@apps_app.command("show")
def apps_show(ctx: typer.Context, app_ref: str):
    runtime = _state(ctx)
    item = runtime.store.get_app(app_ref)
    console.print_json(
        json.dumps(
            {
                "name": item.name,
                "app_id": item.app_id,
                "ai_agent_id": item.ai_agent_id,
                "active_cluster_id": item.active_cluster_id,
                "config_path": item.config_path,
                "config_key": item.config_key,
                "project_path": item.project_path,
                "explanation": item.explanation,
            }
        )
    )


@apps_app.command("add-custom")
def apps_add_custom(
    ctx: typer.Context,
    name: str,
    config_path: Path,
    config_key: str = "mcpServers",
    ai_agent_id: str = "custom",
    explanation: str = "Custom app",
):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    item = runtime.store.create_app(
        name,
        ai_agent_id=ai_agent_id,
        config_path=str(config_path.expanduser()),
        config_key=config_key,
        explanation=explanation,
    )
    console.print(f"Created app {item.name} ({item.app_id})")


@apps_app.command("set-active-cluster")
def apps_set_active_cluster(ctx: typer.Context, app_ref: str, cluster_ref: str):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    item = runtime.store.set_active_cluster(app_ref, cluster_ref)
    console.print(f"{item.name} active cluster -> {item.active_cluster_id}")


@clusters_app.command("list")
def clusters_list(ctx: typer.Context, app_name: str | None = typer.Option(None, "--app")):
    runtime = _state(ctx)
    table = Table("App PK", "Name", "Cluster ID", "Enabled")
    for cluster in runtime.store.list_clusters(app_name):
        table.add_row(
            str(cluster.app_pk),
            cluster.name,
            cluster.cluster_id,
            str(len(cluster.enabled_server_ids)),
        )
    console.print(table)


@clusters_app.command("show")
def clusters_show(ctx: typer.Context, cluster_ref: str, app_name: str = typer.Option(..., "--app")):
    runtime = _state(ctx)
    cluster = runtime.store.get_cluster(app_name, cluster_ref)
    console.print_json(
        json.dumps(
            {
                "name": cluster.name,
                "cluster_id": cluster.cluster_id,
                "app_pk": cluster.app_pk,
                "enabled_server_ids": cluster.enabled_server_ids,
            }
        )
    )


@clusters_app.command("create")
def clusters_create(ctx: typer.Context, name: str, app_name: str = typer.Option(..., "--app")):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    cluster = runtime.store.create_cluster(app_name, name)
    console.print(f"Created cluster {cluster.name} ({cluster.cluster_id})")


@clusters_app.command("rename")
def clusters_rename(
    ctx: typer.Context,
    cluster_ref: str,
    new_name: str,
    app_name: str = typer.Option(..., "--app"),
):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    cluster = runtime.store.rename_cluster(app_name, cluster_ref, new_name)
    console.print(f"Renamed cluster -> {cluster.name}")


@clusters_app.command("delete")
def clusters_delete(
    ctx: typer.Context,
    cluster_ref: str,
    app_name: str = typer.Option(..., "--app"),
):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    runtime.store.delete_cluster(app_name, cluster_ref)
    console.print(f"Deleted cluster {cluster_ref}")


@servers_app.command("list")
def servers_list(ctx: typer.Context, source: str | None = typer.Option(None, "--source")):
    runtime = _state(ctx)
    table = Table("Name", "ID", "Source", "Type", "Command", "URL")
    for item in runtime.store.list_servers():
        if source and item.source.casefold() != source.casefold():
            continue
        table.add_row(
            item.name,
            item.server_id,
            item.source,
            item.server_type,
            item.command or "",
            item.url or "",
        )
    console.print(table)


@servers_app.command("show")
def servers_show(ctx: typer.Context, server_ref: str):
    runtime = _state(ctx)
    item = runtime.store.get_server(server_ref)
    console.print_json(
        json.dumps(server_to_config_dict(item) | {"name": item.name, "server_id": item.server_id})
    )


@servers_app.command("add")
def servers_add(
    ctx: typer.Context,
    name: str,
    command: str | None = typer.Option(None, "--command"),
    arg: list[str] = typer.Option(None, "--arg"),
    env: list[str] = typer.Option(None, "--env"),
    header: list[str] = typer.Option(None, "--header"),
    parameter: list[str] = typer.Option(None, "--parameter"),
    url: str | None = typer.Option(None, "--url"),
    server_type: str = typer.Option("STDIO", "--type"),
    source: str = typer.Option("imported", "--source"),
    version: str = typer.Option("1.0.0", "--version"),
    server_id: str | None = typer.Option(None, "--server-id"),
):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    item = runtime.store.add_server(
        name=name,
        command=command,
        args=arg,
        env=_parse_pairs(env or []),
        headers=_parse_pairs(header or []),
        parameters=_parse_pairs(parameter or []),
        url=url,
        server_type=server_type,
        source=source,
        version=version,
        server_id=server_id,
    )
    console.print(f"Added server {item.name} ({item.server_id})")


@servers_app.command("update")
def servers_update(
    ctx: typer.Context,
    server_ref: str,
    name: str | None = typer.Option(None, "--name"),
    command: str | None = typer.Option(None, "--command"),
    arg: list[str] = typer.Option(None, "--arg"),
    env: list[str] = typer.Option(None, "--env"),
    header: list[str] = typer.Option(None, "--header"),
    url: str | None = typer.Option(None, "--url"),
    server_type: str | None = typer.Option(None, "--type"),
    source: str | None = typer.Option(None, "--source"),
    version: str | None = typer.Option(None, "--version"),
):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    item = runtime.store.update_server(
        server_ref,
        name=name,
        command=command,
        args=arg,
        env=_parse_pairs(env) if env else None,
        headers=_parse_pairs(header) if header else None,
        url=url,
        server_type=server_type,
        source=source,
        version=version,
    )
    console.print(f"Updated server {item.name} ({item.server_id})")


@servers_app.command("delete")
def servers_delete(ctx: typer.Context, server_ref: str):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    runtime.store.delete_server(server_ref)
    console.print(f"Deleted server {server_ref}")


@servers_app.command("enable")
def servers_enable(
    ctx: typer.Context,
    server_ref: list[str],
    cluster: str = typer.Option(..., "--cluster"),
    app_name: str = typer.Option(..., "--app"),
):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    updated = runtime.store.enable_servers(app_name, cluster, server_ref)
    console.print(f"{updated.name}: enabled {len(updated.enabled_server_ids)} servers")


@servers_app.command("enable-many")
def servers_enable_many(
    ctx: typer.Context,
    server_ref: list[str],
    target: list[str] = typer.Option(..., "--target"),
):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    applied_targets: list[str] = []
    for raw_target in target:
        app_name, cluster_name = _parse_target(raw_target)
        runtime.store.enable_servers(app_name, cluster_name, server_ref)
        applied_targets.append(f"{app_name}/{cluster_name}")

    console.print(
        f"Enabled {len(server_ref)} server(s) across {len(applied_targets)} target cluster(s): "
        + ", ".join(applied_targets)
    )


@servers_app.command("disable")
def servers_disable(
    ctx: typer.Context,
    server_ref: list[str],
    cluster: str = typer.Option(..., "--cluster"),
    app_name: str = typer.Option(..., "--app"),
):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    updated = runtime.store.disable_servers(app_name, cluster, server_ref)
    console.print(f"{updated.name}: enabled {len(updated.enabled_server_ids)} servers")


@market_app.command("list")
def market_list(ctx: typer.Context, category: str | None = typer.Option(None, "--category")):
    runtime = _state(ctx)
    tools = load_market_catalog(runtime.resources_dir)
    table = Table("Name", "Category", "Version", "Connections", "GitHub")
    for tool in tools:
        if category and tool.category.casefold() != category.casefold():
            continue
        table.add_row(
            tool.name,
            tool.category,
            tool.version or "",
            ", ".join(connection.type for connection in tool.connections),
            tool.github_url or "",
        )
    console.print(table)


@market_app.command("show")
def market_show(ctx: typer.Context, tool_ref: str):
    runtime = _state(ctx)
    tool = find_market_tool(load_market_catalog(runtime.resources_dir), tool_ref)
    console.print_json(
        json.dumps(
            {
                "name": tool.name,
                "category": tool.category,
                "catalog_id": tool.catalog_id,
                "version": tool.version,
                "author": tool.author,
                "explanation": tool.explanation,
                "github_url": tool.github_url,
                "package_url": tool.package_url,
                "connections": [connection.__dict__ for connection in tool.connections],
            }
        )
    )


@market_app.command("install")
def market_install(
    ctx: typer.Context,
    tool_ref: str,
    app_name: str = typer.Option(..., "--app"),
    cluster: str = typer.Option(..., "--cluster"),
    connection_type: str | None = typer.Option(None, "--connection"),
    parameter: list[str] = typer.Option(None, "--param"),
    version: str | None = typer.Option(None, "--version"),
):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    tool = find_market_tool(load_market_catalog(runtime.resources_dir), tool_ref)
    connection = choose_connection(tool, connection_type)
    materialized = materialize_connection(tool, connection, _parse_pairs(parameter or []), version)
    server = runtime.store.add_server(
        name=str(materialized["name"]),
        command=materialized.get("command"),
        args=list(materialized.get("args", [])),
        headers=dict(materialized.get("headers", {})),
        parameters=dict(materialized.get("parameters", {})),
        source=str(materialized.get("source", "market")),
        server_type=str(materialized.get("server_type", "STDIO")),
        url=materialized.get("url"),
        version=str(materialized.get("version", "latest")),
        server_id=generate_server_id(f"{tool.catalog_id}|{tool.name}"),
    )
    runtime.store.enable_servers(app_name, cluster, [server.server_id])
    console.print(f"Installed {server.name} ({server.server_id}) into {app_name}/{cluster}")


def _sync_single_app(runtime: Runtime, app_ref: str) -> str:
    target = runtime.store.get_app(app_ref)
    if not target.config_path or not target.config_key:
        raise typer.BadParameter(f"App has no config target: {target.name}")
    cluster_id = target.active_cluster_id
    if not cluster_id:
        raise typer.BadParameter(f"App has no active cluster: {target.name}")
    cluster = runtime.store.get_cluster(target.name, cluster_id)
    servers = runtime.store.get_servers_by_ids(cluster.enabled_server_ids)
    output = enabled_servers_to_config(target, servers)
    write_config_map(Path(target.config_path).expanduser(), target.config_key, output)
    return f"Synced {target.name} -> {target.config_path}"


@sync_app.command("app")
def sync_one(ctx: typer.Context, app_ref: str):
    runtime = _state(ctx)
    message = _sync_single_app(runtime, app_ref)
    console.print(message)


@sync_app.command("all")
def sync_all(ctx: typer.Context):
    runtime = _state(ctx)
    for item in runtime.store.list_apps():
        if item.config_path and item.config_key and item.active_cluster_id:
            console.print(_sync_single_app(runtime, item.name))


def _import_mapping(
    runtime: Runtime, app_ref: str, path: Path | None = None, key: str | None = None
) -> int:
    app_record = runtime.store.get_app(app_ref)
    target_path = path or Path(app_record.config_path or "")
    target_key = key or app_record.config_key
    if not target_path or not target_key:
        raise typer.BadParameter("Import target requires a config path and key")

    imported = 0
    for raw_name, payload in load_config_map(target_path.expanduser(), target_key).items():
        name, extracted_id = parse_server_key(raw_name)
        command = payload.get("command")
        args = list(payload.get("args", []))
        env = dict(payload.get("env", {}))
        headers = dict(payload.get("headers", {}))
        url = payload.get("url")
        server_id = extracted_id or generate_server_id(f"{name}|{command}|{url}|{' '.join(args)}")
        try:
            runtime.store.get_server(server_id)
        except KeyError:
            runtime.store.add_server(
                name=name,
                command=command,
                args=args,
                env=env,
                headers=headers,
                url=url,
                source="imported",
                server_type="STREAMABLE_HTTP" if url and not command else "STDIO",
                server_id=server_id,
            )
            imported += 1
    return imported


@import_app.command("app")
def import_from_app(ctx: typer.Context, app_ref: str):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    count = _import_mapping(runtime, app_ref)
    console.print(f"Imported {count} server(s) from {app_ref}")


@import_app.command("file")
def import_from_file(
    ctx: typer.Context,
    app_ref: str,
    path: Path = typer.Option(..., "--path"),
    key: str = typer.Option(..., "--key"),
):
    runtime = _state(ctx)
    _backup_if_needed(runtime)
    count = _import_mapping(runtime, app_ref, path, key)
    console.print(f"Imported {count} server(s) from {path}")


@app.command("doctor")
def doctor(ctx: typer.Context):
    runtime = _state(ctx)
    tools = load_market_catalog(runtime.resources_dir) if runtime.resources_dir.exists() else []
    table = Table("Check", "Value")
    table.add_row("DB path", str(runtime.store.db_path))
    table.add_row("DB exists", str(runtime.store.db_path.exists()))
    table.add_row("Resources dir", str(runtime.resources_dir))
    table.add_row("Resources dir exists", str(runtime.resources_dir.exists()))
    table.add_row("Market tool count", str(len(tools)))
    table.add_row(
        "App count", str(len(runtime.store.list_apps())) if runtime.store.db_path.exists() else "0"
    )
    console.print(table)


def main() -> None:
    app()

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
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
)
apps_app = typer.Typer(help="Manage McpOne apps.", invoke_without_command=True)
clusters_app = typer.Typer(help="Manage McpOne clusters.", invoke_without_command=True)
servers_app = typer.Typer(help="Manage McpOne servers.", invoke_without_command=True)
market_app = typer.Typer(help="Inspect and install market tools.", invoke_without_command=True)
sync_app = typer.Typer(
    help="Sync McpOne state to agent config files.",
    invoke_without_command=True,
)
import_app = typer.Typer(help="Import agent config files into McpOne.", invoke_without_command=True)

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
    json_output: bool


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


def _emit_json(payload: object) -> None:
    console.print_json(json.dumps(payload))


def _emit(
    runtime: Runtime,
    *,
    payload: object,
    table: Table | None = None,
    text: str | None = None,
) -> None:
    if runtime.json_output:
        _emit_json(payload)
        return
    if table is not None:
        console.print(table)
        return
    if text is not None:
        console.print(text)
    elif isinstance(payload, str):
        console.print(payload)
    else:
        _emit_json(payload)


def _command_entries(ctx: typer.Context) -> list[dict[str, str]]:
    command = ctx.command
    commands = getattr(command, "commands", {})
    return [
        {"name": name, "help": subcommand.get_short_help_str()}
        for name, subcommand in sorted(commands.items())
    ]


def _help_payload(ctx: typer.Context) -> dict[str, object]:
    return {
        "group": "mcpone-cli"
        if (ctx.info_name or "") == "root"
        else (ctx.info_name or "mcpone-cli"),
        "help": ctx.command.help,
        "usage": ctx.get_usage().strip(),
        "commands": _command_entries(ctx),
    }


def _app_payload(item) -> dict[str, object]:
    return {
        "name": item.name,
        "app_id": item.app_id,
        "ai_agent_id": item.ai_agent_id,
        "active_cluster_id": item.active_cluster_id,
        "config_path": item.config_path,
        "config_key": item.config_key,
        "project_path": item.project_path,
        "explanation": item.explanation,
    }


def _cluster_payload(item, app_name: str | None = None) -> dict[str, object]:
    payload = {
        "name": item.name,
        "cluster_id": item.cluster_id,
        "app_pk": item.app_pk,
        "enabled_server_ids": item.enabled_server_ids,
    }
    if app_name is not None:
        payload["app_name"] = app_name
    return payload


def _server_payload(item) -> dict[str, object]:
    return server_to_config_dict(item) | {
        "name": item.name,
        "server_id": item.server_id,
        "source": item.source,
        "server_type": item.server_type,
        "version": item.version,
        "headers": item.headers,
        "parameters": item.parameters,
        "custom_fields": item.custom_fields,
    }


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    table = Table("Field", "Value")
    for key, value in rows:
        table.add_row(key, value)
    return table


def _backup_if_needed(runtime: Runtime) -> str | None:
    if runtime.backup_on_write and runtime.store.db_path.exists():
        backup_path = runtime.store.backup()
        if not runtime.json_output:
            console.print(f"[dim]DB backup:[/dim] {backup_path}")
        return str(backup_path)
    return None


def _runtime_from_ctx(ctx: typer.Context) -> Runtime | None:
    if isinstance(ctx.obj, Runtime):
        return ctx.obj
    parent = ctx.parent
    while parent is not None:
        if isinstance(parent.obj, Runtime):
            return parent.obj
        parent = parent.parent
    return None


def _group_help_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        runtime = _runtime_from_ctx(ctx)
        if runtime is None:
            console.print(ctx.get_help())
            raise typer.Exit()
        if runtime.json_output:
            _emit_json(_help_payload(ctx))
        else:
            console.print(ctx.get_help())
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
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON output.",
    ),
    version: bool = typer.Option(False, "--version", help="Show the mcpone-cli version and exit."),
):
    settings = load_settings(config)
    ctx.obj = Runtime(
        store=McpOneStore(settings.db_path),
        resources_dir=settings.resources_dir,
        backup_on_write=settings.backup_on_write,
        json_output=json_output,
    )
    runtime = _state(ctx)
    if version:
        _emit(runtime, payload={"version": __version__}, text=__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        if runtime.json_output:
            _emit_json(_help_payload(ctx))
        else:
            console.print(ctx.get_help())
        raise typer.Exit()


@apps_app.callback()
def apps_callback(ctx: typer.Context) -> None:
    _group_help_callback(ctx)


@clusters_app.callback()
def clusters_callback(ctx: typer.Context) -> None:
    _group_help_callback(ctx)


@servers_app.callback()
def servers_callback(ctx: typer.Context) -> None:
    _group_help_callback(ctx)


@market_app.callback()
def market_callback(ctx: typer.Context) -> None:
    _group_help_callback(ctx)


@sync_app.callback()
def sync_callback(ctx: typer.Context) -> None:
    _group_help_callback(ctx)


@import_app.callback()
def import_callback(ctx: typer.Context) -> None:
    _group_help_callback(ctx)


@apps_app.command("list")
def apps_list(ctx: typer.Context):
    runtime = _state(ctx)
    items = runtime.store.list_apps()
    cluster_names_by_app = {
        item.name: {
            cluster.cluster_id: cluster.name for cluster in runtime.store.list_clusters(item.name)
        }
        for item in items
    }
    table = Table("Name", "Agent", "Active Cluster", "Config")
    for item in items:
        table.add_row(
            item.name,
            item.ai_agent_id or "",
            cluster_names_by_app.get(item.name, {}).get(item.active_cluster_id or "", ""),
            item.config_path or "",
        )
    _emit(
        runtime,
        payload={"apps": [_app_payload(item) for item in items], "count": len(items)},
        table=table,
    )


@apps_app.command("show", no_args_is_help=True)
def apps_show(ctx: typer.Context, app_ref: str):
    runtime = _state(ctx)
    item = runtime.store.get_app(app_ref)
    active_cluster_name = ""
    if item.active_cluster_id:
        clusters_by_id = {
            cluster.cluster_id: cluster.name for cluster in runtime.store.list_clusters(item.name)
        }
        active_cluster_name = clusters_by_id.get(item.active_cluster_id, "")
    _emit(
        runtime,
        payload=_app_payload(item),
        table=_kv_table(
            [
                ("Name", item.name),
                ("Agent", item.ai_agent_id or ""),
                ("Active Cluster", active_cluster_name),
                ("Config Path", item.config_path or ""),
                ("Config Key", item.config_key or ""),
                ("Project Path", item.project_path or ""),
                ("Explanation", item.explanation or ""),
            ]
        ),
    )


@apps_app.command("matrix", no_args_is_help=True)
def apps_matrix(
    ctx: typer.Context,
    app_ref: str,
    enabled_only: bool = typer.Option(
        False,
        "--enabled-only",
        help="Only show servers enabled in at least one cluster for the app.",
    ),
):
    runtime = _state(ctx)
    app_item = runtime.store.get_app(app_ref)
    clusters = sorted(
        runtime.store.list_clusters(app_item.name), key=lambda item: item.name.casefold()
    )
    if not clusters:
        raise typer.BadParameter(f"App has no clusters: {app_item.name}")

    server_ids_by_cluster = {
        cluster.cluster_id: set(cluster.enabled_server_ids) for cluster in clusters
    }
    enabled_server_ids = {
        server_id for cluster in clusters for server_id in cluster.enabled_server_ids
    }
    servers = runtime.store.list_servers()
    if enabled_only:
        servers = [server for server in servers if server.server_id in enabled_server_ids]

    table = Table("Server")
    for cluster in clusters:
        label = cluster.name
        if app_item.active_cluster_id == cluster.cluster_id:
            label = f"{label} (active)"
        table.add_column(label)

    for server in servers:
        row = [server.name]
        for cluster in clusters:
            row.append("Y" if server.server_id in server_ids_by_cluster[cluster.cluster_id] else "")
        table.add_row(*row)
    _emit(
        runtime,
        payload={
            "app": _app_payload(app_item),
            "clusters": [
                {
                    "name": cluster.name,
                    "cluster_id": cluster.cluster_id,
                    "is_active": app_item.active_cluster_id == cluster.cluster_id,
                }
                for cluster in clusters
            ],
            "servers": [
                {
                    "name": server.name,
                    "server_id": server.server_id,
                    "enabled_in_clusters": [
                        cluster.cluster_id
                        for cluster in clusters
                        if server.server_id in server_ids_by_cluster[cluster.cluster_id]
                    ],
                    "cluster_states": {
                        cluster.cluster_id: server.server_id
                        in server_ids_by_cluster[cluster.cluster_id]
                        for cluster in clusters
                    },
                }
                for server in servers
            ],
            "count": len(servers),
        },
        table=table,
    )


@apps_app.command("add-custom", no_args_is_help=True)
def apps_add_custom(
    ctx: typer.Context,
    name: str,
    config_path: Path,
    config_key: str = "mcpServers",
    ai_agent_id: str = "custom",
    explanation: str = "Custom app",
):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    item = runtime.store.create_app(
        name,
        ai_agent_id=ai_agent_id,
        config_path=str(config_path.expanduser()),
        config_key=config_key,
        explanation=explanation,
    )
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "apps.add-custom",
            "backup_path": backup_path,
            "app": _app_payload(item),
        },
        text=f"Created app {item.name}",
    )


@apps_app.command("set-active-cluster", no_args_is_help=True)
def apps_set_active_cluster(ctx: typer.Context, app_ref: str, cluster_ref: str):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    item = runtime.store.set_active_cluster(app_ref, cluster_ref)
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "apps.set-active-cluster",
            "backup_path": backup_path,
            "app": _app_payload(item),
        },
        text=f"{item.name} active cluster -> {cluster_ref}",
    )


@clusters_app.command("list")
def clusters_list(ctx: typer.Context, app_name: str | None = typer.Option(None, "--app")):
    runtime = _state(ctx)
    apps_by_pk = {item.pk: item.name for item in runtime.store.list_apps()}
    clusters = sorted(
        runtime.store.list_clusters(app_name),
        key=lambda item: (apps_by_pk.get(item.app_pk, ""), item.name.casefold()),
    )
    table = Table("App", "Name", "Enabled")
    for cluster in clusters:
        table.add_row(
            apps_by_pk.get(cluster.app_pk, str(cluster.app_pk)),
            cluster.name,
            str(len(cluster.enabled_server_ids)),
        )
    _emit(
        runtime,
        payload={
            "clusters": [
                _cluster_payload(cluster, apps_by_pk.get(cluster.app_pk, str(cluster.app_pk)))
                for cluster in clusters
            ],
            "count": len(clusters),
        },
        table=table,
    )


@clusters_app.command("show", no_args_is_help=True)
def clusters_show(ctx: typer.Context, cluster_ref: str, app_name: str = typer.Option(..., "--app")):
    runtime = _state(ctx)
    cluster = runtime.store.get_cluster(app_name, cluster_ref)
    _emit(
        runtime,
        payload=_cluster_payload(cluster, app_name),
        table=_kv_table(
            [
                ("App", app_name),
                ("Name", cluster.name),
                ("Enabled Servers", str(len(cluster.enabled_server_ids))),
            ]
        ),
    )


@clusters_app.command("create", no_args_is_help=True)
def clusters_create(ctx: typer.Context, name: str, app_name: str = typer.Option(..., "--app")):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    cluster = runtime.store.create_cluster(app_name, name)
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "clusters.create",
            "backup_path": backup_path,
            "cluster": _cluster_payload(cluster, app_name),
        },
        text=f"Created cluster {cluster.name} for {app_name}",
    )


@clusters_app.command("rename", no_args_is_help=True)
def clusters_rename(
    ctx: typer.Context,
    cluster_ref: str,
    new_name: str,
    app_name: str = typer.Option(..., "--app"),
):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    cluster = runtime.store.rename_cluster(app_name, cluster_ref, new_name)
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "clusters.rename",
            "backup_path": backup_path,
            "cluster": _cluster_payload(cluster, app_name),
        },
        text=f"Renamed cluster -> {cluster.name}",
    )


@clusters_app.command("delete", no_args_is_help=True)
def clusters_delete(
    ctx: typer.Context,
    cluster_ref: str,
    app_name: str = typer.Option(..., "--app"),
):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    runtime.store.delete_cluster(app_name, cluster_ref)
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "clusters.delete",
            "backup_path": backup_path,
            "app_name": app_name,
            "cluster_ref": cluster_ref,
        },
        text=f"Deleted cluster {cluster_ref}",
    )


@servers_app.command("list")
def servers_list(ctx: typer.Context, source: str | None = typer.Option(None, "--source")):
    runtime = _state(ctx)
    items = []
    table = Table("Name", "Source", "Type", "Command", "URL")
    for item in runtime.store.list_servers():
        if source and item.source.casefold() != source.casefold():
            continue
        items.append(item)
        table.add_row(
            item.name,
            item.source,
            item.server_type,
            item.command or "",
            item.url or "",
        )
    _emit(
        runtime,
        payload={"servers": [_server_payload(item) for item in items], "count": len(items)},
        table=table,
    )


@servers_app.command("show", no_args_is_help=True)
def servers_show(ctx: typer.Context, server_ref: str):
    runtime = _state(ctx)
    item = runtime.store.get_server(server_ref)
    _emit(
        runtime,
        payload=_server_payload(item),
        table=_kv_table(
            [
                ("Name", item.name),
                ("Source", item.source),
                ("Type", item.server_type),
                ("Command", item.command or ""),
                ("URL", item.url or ""),
                ("Version", item.version or ""),
                ("Args", _stringify(item.args)),
                ("Env", _stringify(item.env)),
                ("Headers", _stringify(item.headers)),
                ("Parameters", _stringify(item.parameters)),
                ("Custom Fields", _stringify(item.custom_fields)),
            ]
        ),
    )


@servers_app.command("add", no_args_is_help=True)
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
    backup_path = _backup_if_needed(runtime)
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
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "servers.add",
            "backup_path": backup_path,
            "server": _server_payload(item),
        },
        text=f"Added server {item.name}",
    )


@servers_app.command("update", no_args_is_help=True)
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
    backup_path = _backup_if_needed(runtime)
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
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "servers.update",
            "backup_path": backup_path,
            "server": _server_payload(item),
        },
        text=f"Updated server {item.name}",
    )


@servers_app.command("delete", no_args_is_help=True)
def servers_delete(ctx: typer.Context, server_ref: str):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    runtime.store.delete_server(server_ref)
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "servers.delete",
            "backup_path": backup_path,
            "server_ref": server_ref,
        },
        text=f"Deleted server {server_ref}",
    )


@servers_app.command("enable", no_args_is_help=True)
def servers_enable(
    ctx: typer.Context,
    server_ref: list[str],
    cluster: str = typer.Option(..., "--cluster"),
    app_name: str = typer.Option(..., "--app"),
):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    updated = runtime.store.enable_servers(app_name, cluster, server_ref)
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "servers.enable",
            "backup_path": backup_path,
            "cluster": _cluster_payload(updated, app_name),
            "server_refs": server_ref,
        },
        text=f"{updated.name}: enabled {len(updated.enabled_server_ids)} servers",
    )


@servers_app.command("enable-many", no_args_is_help=True)
def servers_enable_many(
    ctx: typer.Context,
    server_ref: list[str],
    target: list[str] = typer.Option(..., "--target"),
):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    applied_targets: list[str] = []
    for raw_target in target:
        app_name, cluster_name = _parse_target(raw_target)
        runtime.store.enable_servers(app_name, cluster_name, server_ref)
        applied_targets.append(f"{app_name}/{cluster_name}")
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "servers.enable-many",
            "backup_path": backup_path,
            "server_refs": server_ref,
            "targets": applied_targets,
            "count": len(applied_targets),
        },
        text=(
            f"Enabled {len(server_ref)} server(s) across {len(applied_targets)} target cluster(s): "
            + ", ".join(applied_targets)
        ),
    )


@servers_app.command("disable", no_args_is_help=True)
def servers_disable(
    ctx: typer.Context,
    server_ref: list[str],
    cluster: str = typer.Option(..., "--cluster"),
    app_name: str = typer.Option(..., "--app"),
):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    updated = runtime.store.disable_servers(app_name, cluster, server_ref)
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "servers.disable",
            "backup_path": backup_path,
            "cluster": _cluster_payload(updated, app_name),
            "server_refs": server_ref,
        },
        text=f"{updated.name}: enabled {len(updated.enabled_server_ids)} servers",
    )


@market_app.command("list")
def market_list(ctx: typer.Context, category: str | None = typer.Option(None, "--category")):
    runtime = _state(ctx)
    tools = load_market_catalog(runtime.resources_dir)
    table = Table("Name", "Category", "Version", "Connections", "GitHub")
    filtered_tools = []
    for tool in tools:
        if category and tool.category.casefold() != category.casefold():
            continue
        filtered_tools.append(tool)
        table.add_row(
            tool.name,
            tool.category,
            tool.version or "",
            ", ".join(connection.type for connection in tool.connections),
            tool.github_url or "",
        )
    _emit(
        runtime,
        payload={
            "tools": [
                {
                    "name": tool.name,
                    "category": tool.category,
                    "catalog_id": tool.catalog_id,
                    "version": tool.version,
                    "github_url": tool.github_url,
                    "connections": [asdict(connection) for connection in tool.connections],
                }
                for tool in filtered_tools
            ],
            "count": len(filtered_tools),
        },
        table=table,
    )


@market_app.command("show", no_args_is_help=True)
def market_show(ctx: typer.Context, tool_ref: str):
    runtime = _state(ctx)
    tool = find_market_tool(load_market_catalog(runtime.resources_dir), tool_ref)
    _emit(
        runtime,
        payload={
            "name": tool.name,
            "category": tool.category,
            "catalog_id": tool.catalog_id,
            "version": tool.version,
            "author": tool.author,
            "explanation": tool.explanation,
            "github_url": tool.github_url,
            "package_url": tool.package_url,
            "connections": [asdict(connection) for connection in tool.connections],
        },
        table=_kv_table(
            [
                ("Name", tool.name),
                ("Category", tool.category),
                ("Version", tool.version or ""),
                ("Author", tool.author or ""),
                ("GitHub", tool.github_url or ""),
                ("Package", tool.package_url or ""),
                ("Connections", ", ".join(connection.type for connection in tool.connections)),
                ("Explanation", tool.explanation or ""),
            ]
        ),
    )


@market_app.command("install", no_args_is_help=True)
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
    backup_path = _backup_if_needed(runtime)
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
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "market.install",
            "backup_path": backup_path,
            "app_name": app_name,
            "cluster_name": cluster,
            "tool": {
                "name": tool.name,
                "catalog_id": tool.catalog_id,
                "connection_type": connection.type,
            },
            "server": _server_payload(server),
        },
        text=f"Installed {server.name} into {app_name}/{cluster}",
    )


def _sync_single_app(runtime: Runtime, app_ref: str) -> dict[str, object]:
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
    return {
        "app": _app_payload(target),
        "cluster": _cluster_payload(cluster, target.name),
        "config_path": target.config_path,
        "config_key": target.config_key,
        "server_count": len(servers),
    }


@sync_app.command("app", no_args_is_help=True)
def sync_one(ctx: typer.Context, app_ref: str):
    runtime = _state(ctx)
    payload = _sync_single_app(runtime, app_ref)
    _emit(
        runtime,
        payload={"status": "ok", "action": "sync.app"} | payload,
        text=f"Synced {payload['app']['name']} -> {payload['config_path']}",
    )


@sync_app.command("all")
def sync_all(ctx: typer.Context):
    runtime = _state(ctx)
    synced = []
    for item in runtime.store.list_apps():
        if item.config_path and item.config_key and item.active_cluster_id:
            synced.append(_sync_single_app(runtime, item.name))
    _emit(
        runtime,
        payload={"synced": synced, "count": len(synced)},
        text="\n".join(f"Synced {item['app']['name']} -> {item['config_path']}" for item in synced),
    )


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


@import_app.command("app", no_args_is_help=True)
def import_from_app(ctx: typer.Context, app_ref: str):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    count = _import_mapping(runtime, app_ref)
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "import.app",
            "backup_path": backup_path,
            "app_ref": app_ref,
            "imported_count": count,
        },
        text=f"Imported {count} server(s) from {app_ref}",
    )


@import_app.command("file", no_args_is_help=True)
def import_from_file(
    ctx: typer.Context,
    app_ref: str,
    path: Path = typer.Option(..., "--path"),
    key: str = typer.Option(..., "--key"),
):
    runtime = _state(ctx)
    backup_path = _backup_if_needed(runtime)
    count = _import_mapping(runtime, app_ref, path, key)
    _emit(
        runtime,
        payload={
            "status": "ok",
            "action": "import.file",
            "backup_path": backup_path,
            "app_ref": app_ref,
            "path": str(path),
            "key": key,
            "imported_count": count,
        },
        text=f"Imported {count} server(s) from {path}",
    )


@app.command("doctor")
def doctor(ctx: typer.Context):
    runtime = _state(ctx)
    tools = load_market_catalog(runtime.resources_dir) if runtime.resources_dir.exists() else []
    table = Table("Check", "Value")
    checks = {
        "db_path": str(runtime.store.db_path),
        "db_exists": runtime.store.db_path.exists(),
        "resources_dir": str(runtime.resources_dir),
        "resources_dir_exists": runtime.resources_dir.exists(),
        "market_tool_count": len(tools),
        "app_count": len(runtime.store.list_apps()) if runtime.store.db_path.exists() else 0,
    }
    for key, value in checks.items():
        table.add_row(key, str(value))
    _emit(runtime, payload={"checks": checks}, table=table)


def main() -> None:
    app()

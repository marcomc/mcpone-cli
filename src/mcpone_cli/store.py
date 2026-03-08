from __future__ import annotations

import json
import shutil
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from uuid import uuid4

from .models import AddedApp, AddedServer, Cluster, JsonDict

APPLE_EPOCH_OFFSET = 978307200.0
DEFAULT_ENTITY_IDS = {"ZADDEDAPP": 1, "ZADDEDSERVER": 2, "ZCLUSTER": 3}


def apple_timestamp_now() -> float:
    return time.time() - APPLE_EPOCH_OFFSET


def decode_blob(blob: bytes | str | memoryview | None, fallback: object) -> object:
    if not blob:
        return fallback
    try:
        if isinstance(blob, str):
            text = blob
        elif isinstance(blob, memoryview):
            text = blob.tobytes().decode("utf-8")
        else:
            text = blob.decode("utf-8")
        return json.loads(text)
    except (AttributeError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return fallback


def encode_blob(value: object) -> bytes:
    return json.dumps(value).encode("utf-8")


def generate_server_id(seed: str) -> str:
    digest = sha1(seed.encode("utf-8")).digest()
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    number = int.from_bytes(digest[:6], "big")
    output = []
    while number:
        number, remainder = divmod(number, 36)
        output.append(alphabet[remainder])
    value = "".join(reversed(output or ["0"]))
    return value.rjust(6, "0")[:6]


class McpOneStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def backup(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = self.db_path.with_suffix(f"{self.db_path.suffix}.bak-{stamp}")
        shutil.copy2(self.db_path, destination)
        return destination

    def _next_pk(self, connection: sqlite3.Connection, table: str) -> int:
        row = connection.execute(
            f"SELECT COALESCE(MAX(Z_PK), 0) + 1 AS next_pk FROM {table}"
        ).fetchone()
        return int(row["next_pk"])

    def _entity_id(self, connection: sqlite3.Connection, table: str) -> int:
        row = connection.execute(f"SELECT Z_ENT FROM {table} LIMIT 1").fetchone()
        return int(row["Z_ENT"]) if row else DEFAULT_ENTITY_IDS[table]

    def list_apps(self) -> list[AddedApp]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                  Z_PK, ZNAME, ZID, ZAIAGENTID, ZACTIVECLUSTERID,
                  ZAIAGENTJSONFILEPATH, ZAIAGENTJSONKEY, ZAIAGENTPROJECTPATH, ZEXPLANATION
                FROM ZADDEDAPP
                ORDER BY ZNAME
                """
            ).fetchall()
        return [self._row_to_app(row) for row in rows]

    def get_app(self, ref: str) -> AddedApp:
        needle = ref.casefold()
        for app in self.list_apps():
            if app.name.casefold() == needle or app.app_id.casefold() == needle:
                return app
        raise KeyError(f"App not found: {ref}")

    def list_clusters(self, app_ref: str | None = None) -> list[Cluster]:
        with self.connect() as connection:
            if app_ref:
                app = self.get_app(app_ref)
                rows = connection.execute(
                    """
                    SELECT Z_PK, ZAPP, ZNAME, ZID, ZENABLEDADDEDSERVERIDSDATA
                    FROM ZCLUSTER
                    WHERE ZAPP=?
                    ORDER BY ZNAME
                    """,
                    (app.pk,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT Z_PK, ZAPP, ZNAME, ZID, ZENABLEDADDEDSERVERIDSDATA
                    FROM ZCLUSTER
                    ORDER BY ZAPP, ZNAME
                    """
                ).fetchall()
        return [self._row_to_cluster(row) for row in rows]

    def get_cluster(self, app_ref: str, cluster_ref: str) -> Cluster:
        app = self.get_app(app_ref)
        needle = cluster_ref.casefold()
        for cluster in self.list_clusters(app_ref):
            if cluster.name.casefold() == needle or cluster.cluster_id.casefold() == needle:
                return cluster
        raise KeyError(f"Cluster not found for app {app.name}: {cluster_ref}")

    def list_servers(self) -> list[AddedServer]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                  Z_PK, ZID, ZNAME, ZSOURCE, ZTYPE, ZCOMMAND, ZURL, ZVERSION,
                  ZARGS, ZENV, ZHEADERS, ZPARAMETERS, ZCUSTOMFIELDSBYAGENTDATA
                FROM ZADDEDSERVER
                ORDER BY ZNAME
                """
            ).fetchall()
        return [self._row_to_server(row) for row in rows]

    def get_server(self, ref: str) -> AddedServer:
        needle = ref.casefold()
        for server in self.list_servers():
            if server.name.casefold() == needle or server.server_id.casefold() == needle:
                return server
        raise KeyError(f"Server not found: {ref}")

    def get_servers_by_ids(self, server_ids: list[str]) -> list[AddedServer]:
        wanted = {item.casefold() for item in server_ids}
        return [server for server in self.list_servers() if server.server_id.casefold() in wanted]

    def create_app(
        self,
        name: str,
        *,
        ai_agent_id: str = "custom",
        config_path: str | None = None,
        config_key: str | None = "mcpServers",
        explanation: str = "Custom app",
        project_path: str | None = None,
    ) -> AddedApp:
        app_id = str(uuid4()).upper()
        cluster_id = str(uuid4()).upper()

        with self.connect() as connection:
            now = apple_timestamp_now()
            pk = self._next_pk(connection, "ZADDEDAPP")
            connection.execute(
                """
                INSERT INTO ZADDEDAPP (
                  Z_PK, Z_ENT, Z_OPT, ZHASFILEACCESS, ZRENAMED, ZCREATEDAT, ZUPDATEDAT,
                  ZACTIVECLUSTERID, ZAIAGENTID, ZAIAGENTJSONFILEPATH, ZAIAGENTJSONKEY,
                  ZAIAGENTPROJECTPATH, ZEXPLANATION, ZID, ZNAME, ZHIDDENADDEDSERVERIDSDATA
                ) VALUES (?, ?, 1, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pk,
                    self._entity_id(connection, "ZADDEDAPP"),
                    now,
                    str(now),
                    cluster_id,
                    ai_agent_id,
                    config_path,
                    config_key,
                    project_path,
                    explanation,
                    app_id,
                    name,
                    encode_blob([]),
                ),
            )
            cluster_pk = self._next_pk(connection, "ZCLUSTER")
            connection.execute(
                """
                INSERT INTO ZCLUSTER (
                  Z_PK, Z_ENT, Z_OPT, ZAPP, ZCREATEDAT, ZUPDATEDAT, ZID, ZNAME, ZENABLEDADDEDSERVERIDSDATA
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cluster_pk,
                    self._entity_id(connection, "ZCLUSTER"),
                    pk,
                    now,
                    now,
                    cluster_id,
                    "Cluster A",
                    encode_blob([]),
                ),
            )
        return self.get_app(app_id)

    def create_cluster(self, app_ref: str, name: str) -> Cluster:
        app = self.get_app(app_ref)
        cluster_id = str(uuid4()).upper()
        with self.connect() as connection:
            now = apple_timestamp_now()
            pk = self._next_pk(connection, "ZCLUSTER")
            connection.execute(
                """
                INSERT INTO ZCLUSTER (
                  Z_PK, Z_ENT, Z_OPT, ZAPP, ZCREATEDAT, ZUPDATEDAT, ZID, ZNAME, ZENABLEDADDEDSERVERIDSDATA
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pk,
                    self._entity_id(connection, "ZCLUSTER"),
                    app.pk,
                    now,
                    now,
                    cluster_id,
                    name,
                    encode_blob([]),
                ),
            )
        return self.get_cluster(app.name, cluster_id)

    def rename_cluster(self, app_ref: str, cluster_ref: str, new_name: str) -> Cluster:
        cluster = self.get_cluster(app_ref, cluster_ref)
        with self.connect() as connection:
            connection.execute(
                "UPDATE ZCLUSTER SET ZNAME=?, ZUPDATEDAT=? WHERE Z_PK=?",
                (new_name, apple_timestamp_now(), cluster.pk),
            )
        return self.get_cluster(app_ref, cluster.cluster_id)

    def delete_cluster(self, app_ref: str, cluster_ref: str) -> None:
        app = self.get_app(app_ref)
        cluster = self.get_cluster(app_ref, cluster_ref)
        with self.connect() as connection:
            connection.execute("DELETE FROM ZCLUSTER WHERE Z_PK=?", (cluster.pk,))
            if app.active_cluster_id == cluster.cluster_id:
                connection.execute(
                    "UPDATE ZADDEDAPP SET ZACTIVECLUSTERID=NULL WHERE Z_PK=?", (app.pk,)
                )

    def set_active_cluster(self, app_ref: str, cluster_ref: str) -> AddedApp:
        app = self.get_app(app_ref)
        cluster = self.get_cluster(app_ref, cluster_ref)
        with self.connect() as connection:
            connection.execute(
                "UPDATE ZADDEDAPP SET ZACTIVECLUSTERID=? WHERE Z_PK=?", (cluster.cluster_id, app.pk)
            )
        return self.get_app(app.app_id)

    def add_server(
        self,
        *,
        name: str,
        command: str | None = None,
        args: list[str] | None = None,
        env: JsonDict | None = None,
        headers: JsonDict | None = None,
        parameters: JsonDict | None = None,
        custom_fields: JsonDict | None = None,
        source: str = "imported",
        server_type: str = "STDIO",
        url: str | None = None,
        version: str = "1.0.0",
        server_id: str | None = None,
    ) -> AddedServer:
        resolved_args = args or []
        resolved_env = env or {}
        resolved_headers = headers or {}
        resolved_parameters = parameters or {}
        resolved_custom_fields = custom_fields or {}
        resolved_id = server_id or generate_server_id(
            f"{name}|{command}|{url}|{' '.join(resolved_args)}"
        )

        with self.connect() as connection:
            now = apple_timestamp_now()
            pk = self._next_pk(connection, "ZADDEDSERVER")
            entity_id = self._entity_id(connection, "ZADDEDSERVER")
            payload = (
                pk,
                entity_id,
                now,
                now,
                command,
                resolved_id,
                name,
                "",
                source,
                server_type,
                url,
                version,
                encode_blob(resolved_args),
                encode_blob(resolved_args),
                encode_blob(resolved_custom_fields),
                encode_blob(resolved_env),
                encode_blob(resolved_headers),
                encode_blob(resolved_parameters),
            )
            connection.execute(
                """
                INSERT INTO ZADDEDSERVER (
                  Z_PK, Z_ENT, Z_OPT, ZCREATEDAT, ZUPDATEDAT, ZCOMMAND, ZID, ZNAME, ZSERVERID,
                  ZSOURCE, ZTYPE, ZURL, ZVERSION, ZARGS, ZARGUMENT, ZCUSTOMFIELDSBYAGENTDATA,
                  ZENV, ZHEADERS, ZPARAMETERS
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
        return self.get_server(resolved_id)

    def update_server(self, ref: str, **changes: object) -> AddedServer:
        server = self.get_server(ref)
        current = asdict(server)
        current.update({key: value for key, value in changes.items() if value is not None})
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE ZADDEDSERVER
                SET ZUPDATEDAT=?, ZNAME=?, ZCOMMAND=?, ZSOURCE=?, ZTYPE=?, ZURL=?, ZVERSION=?,
                    ZARGS=?, ZARGUMENT=?, ZENV=?, ZHEADERS=?, ZPARAMETERS=?, ZCUSTOMFIELDSBYAGENTDATA=?
                WHERE Z_PK=?
                """,
                (
                    apple_timestamp_now(),
                    current["name"],
                    current["command"],
                    current["source"],
                    current["server_type"],
                    current["url"],
                    current["version"],
                    encode_blob(current["args"]),
                    encode_blob(current["args"]),
                    encode_blob(current["env"]),
                    encode_blob(current["headers"]),
                    encode_blob(current["parameters"]),
                    encode_blob(current["custom_fields"]),
                    server.pk,
                ),
            )
        return self.get_server(server.server_id)

    def delete_server(self, ref: str) -> None:
        server = self.get_server(ref)
        with self.connect() as connection:
            connection.execute("DELETE FROM ZADDEDSERVER WHERE Z_PK=?", (server.pk,))
            for cluster in self.list_clusters():
                if server.server_id in cluster.enabled_server_ids:
                    enabled = [
                        item for item in cluster.enabled_server_ids if item != server.server_id
                    ]
                    connection.execute(
                        "UPDATE ZCLUSTER SET ZENABLEDADDEDSERVERIDSDATA=?, ZUPDATEDAT=? WHERE Z_PK=?",
                        (encode_blob(enabled), apple_timestamp_now(), cluster.pk),
                    )

    def set_cluster_enabled_servers(
        self,
        app_ref: str,
        cluster_ref: str,
        server_ids: list[str],
    ) -> Cluster:
        cluster = self.get_cluster(app_ref, cluster_ref)
        with self.connect() as connection:
            connection.execute(
                "UPDATE ZCLUSTER SET ZENABLEDADDEDSERVERIDSDATA=?, ZUPDATEDAT=? WHERE Z_PK=?",
                (encode_blob(server_ids), apple_timestamp_now(), cluster.pk),
            )
        return self.get_cluster(app_ref, cluster.cluster_id)

    def enable_servers(self, app_ref: str, cluster_ref: str, refs: list[str]) -> Cluster:
        cluster = self.get_cluster(app_ref, cluster_ref)
        enabled = list(cluster.enabled_server_ids)
        for ref in refs:
            server = self.get_server(ref)
            if server.server_id not in enabled:
                enabled.append(server.server_id)
        return self.set_cluster_enabled_servers(app_ref, cluster_ref, enabled)

    def disable_servers(self, app_ref: str, cluster_ref: str, refs: list[str]) -> Cluster:
        cluster = self.get_cluster(app_ref, cluster_ref)
        remove_ids = {self.get_server(ref).server_id for ref in refs}
        enabled = [
            server_id for server_id in cluster.enabled_server_ids if server_id not in remove_ids
        ]
        return self.set_cluster_enabled_servers(app_ref, cluster_ref, enabled)

    def _row_to_app(self, row: sqlite3.Row) -> AddedApp:
        return AddedApp(
            pk=int(row["Z_PK"]),
            name=str(row["ZNAME"]),
            app_id=str(row["ZID"]),
            ai_agent_id=row["ZAIAGENTID"],
            active_cluster_id=row["ZACTIVECLUSTERID"],
            config_path=row["ZAIAGENTJSONFILEPATH"],
            config_key=row["ZAIAGENTJSONKEY"],
            project_path=row["ZAIAGENTPROJECTPATH"],
            explanation=row["ZEXPLANATION"],
        )

    def _row_to_cluster(self, row: sqlite3.Row) -> Cluster:
        return Cluster(
            pk=int(row["Z_PK"]),
            app_pk=int(row["ZAPP"]),
            name=str(row["ZNAME"]),
            cluster_id=str(row["ZID"]),
            enabled_server_ids=list(decode_blob(row["ZENABLEDADDEDSERVERIDSDATA"], [])),
        )

    def _row_to_server(self, row: sqlite3.Row) -> AddedServer:
        return AddedServer(
            pk=int(row["Z_PK"]),
            server_id=str(row["ZID"]),
            name=str(row["ZNAME"]),
            source=str(row["ZSOURCE"] or ""),
            server_type=str(row["ZTYPE"] or ""),
            command=row["ZCOMMAND"],
            url=row["ZURL"],
            version=row["ZVERSION"],
            args=list(decode_blob(row["ZARGS"], [])),
            env=dict(decode_blob(row["ZENV"], {})),
            headers=dict(decode_blob(row["ZHEADERS"], {})),
            parameters=dict(decode_blob(row["ZPARAMETERS"], {})),
            custom_fields=dict(decode_blob(row["ZCUSTOMFIELDSBYAGENTDATA"], {})),
        )

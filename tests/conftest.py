from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcpone_cli.store import encode_blob


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _create_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE ZADDEDAPP (
          Z_PK INTEGER PRIMARY KEY,
          Z_ENT INTEGER,
          Z_OPT INTEGER,
          ZHASFILEACCESS INTEGER,
          ZRENAMED INTEGER,
          ZCREATEDAT REAL,
          ZACTIVECLUSTERID TEXT,
          ZAIAGENTID TEXT,
          ZAIAGENTJSONFILEPATH TEXT,
          ZAIAGENTJSONKEY TEXT,
          ZAIAGENTPROJECTPATH TEXT,
          ZEXPLANATION TEXT,
          ZID TEXT,
          ZNAME TEXT,
          ZUPDATEDAT TEXT,
          ZHIDDENADDEDSERVERIDSDATA BLOB
        );
        CREATE TABLE ZCLUSTER (
          Z_PK INTEGER PRIMARY KEY,
          Z_ENT INTEGER,
          Z_OPT INTEGER,
          ZAPP INTEGER,
          ZCREATEDAT REAL,
          ZUPDATEDAT REAL,
          ZID TEXT,
          ZNAME TEXT,
          ZENABLEDADDEDSERVERIDSDATA BLOB
        );
        CREATE TABLE ZADDEDSERVER (
          Z_PK INTEGER PRIMARY KEY,
          Z_ENT INTEGER,
          Z_OPT INTEGER,
          ZCREATEDAT REAL,
          ZUPDATEDAT REAL,
          ZCOMMAND TEXT,
          ZID TEXT,
          ZNAME TEXT,
          ZSERVERID TEXT,
          ZSOURCE TEXT,
          ZTYPE TEXT,
          ZURL TEXT,
          ZVERSION TEXT,
          ZARGS BLOB,
          ZARGUMENT BLOB,
          ZCUSTOMFIELDSBYAGENTDATA BLOB,
          ZENV BLOB,
          ZHEADERS BLOB,
          ZPARAMETERS BLOB
        );
        """
    )
    connection.execute(
        """
        INSERT INTO ZADDEDAPP (
          Z_PK, Z_ENT, Z_OPT, ZHASFILEACCESS, ZRENAMED, ZCREATEDAT, ZACTIVECLUSTERID, ZAIAGENTID,
          ZAIAGENTJSONFILEPATH, ZAIAGENTJSONKEY, ZAIAGENTPROJECTPATH, ZEXPLANATION, ZID, ZNAME,
          ZUPDATEDAT, ZHIDDENADDEDSERVERIDSDATA
        ) VALUES (1, 1, 1, 0, 0, 0, 'CLUSTERA', 'codex', ?, 'mcp_servers', '', 'Custom app', 'APP1', 'Codex', '0', ?)
        """,
        (str(path.parent / "codex.toml"), encode_blob([])),
    )
    connection.execute(
        """
        INSERT INTO ZCLUSTER (
          Z_PK, Z_ENT, Z_OPT, ZAPP, ZCREATEDAT, ZUPDATEDAT, ZID, ZNAME, ZENABLEDADDEDSERVERIDSDATA
        ) VALUES (1, 3, 1, 1, 0, 0, 'CLUSTERA', 'Cluster A', ?)
        """,
        (encode_blob([]),),
    )
    connection.commit()
    connection.close()


@pytest.fixture()
def temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "McpOne.sqlite"
    _create_db(db_path)
    return db_path


@pytest.fixture()
def resources_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "Resources"
    directory.mkdir()
    payload = [
        {
            "id": "wotv5q80be",
            "name": "Context7",
            "author": "upstash",
            "category": "development",
            "version": "2.1.0",
            "explanation": "Docs retrieval",
            "githubUrl": "https://github.com/upstash/context7",
            "connections": [
                {
                    "type": "STDIO",
                    "command": "npx",
                    "args": ["-y", "@upstash/context7-mcp@<VERSION>", "<CONTEXT7_API_KEY>"],
                    "parameters": {
                        "CONTEXT7_API_KEY": {
                            "type": "string",
                            "prefix": "--api-key",
                            "displayed": True,
                        }
                    },
                }
            ],
        }
    ]
    (directory / "070_development.json").write_text(json.dumps(payload), encoding="utf-8")
    return directory

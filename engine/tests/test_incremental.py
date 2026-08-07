"""Integration test against a real Postgres (docker-compose.yml).

Skips if no database is reachable — `docker compose up -d` first. Not run
by the CI drift-gate workflow, which only exercises the offline unit and
harness suites.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from avert import db
from avert.index.incremental import incremental_index

DSN = os.environ.get("AVERT_TEST_DATABASE_URL", "postgresql://avert:avert@localhost:5432/avert")


@pytest.fixture
def conn():
    try:
        connection = psycopg.connect(DSN, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip(f"no Postgres reachable at {DSN} — run `docker compose up -d` first")
    connection.execute("DROP SCHEMA public CASCADE")
    connection.execute("CREATE SCHEMA public")
    connection.commit()
    db.apply_migrations(connection)
    yield connection
    connection.close()


def test_index_twice_reparses_nothing(conn, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "llm.py").write_text(
        'from openai import OpenAI\n'
        "client = OpenAI()\n"
        'client.chat.completions.create(model="gpt-4-0613", messages=[])\n'
    )

    first = incremental_index(conn, tmp_path, repo="acme/widgets")
    assert first.parsed == 1
    assert first.skipped == 0
    assert first.call_sites_written == 1

    second = incremental_index(conn, tmp_path, repo="acme/widgets")
    assert second.parsed == 0
    assert second.skipped == 1

    count = conn.execute("SELECT count(*) FROM call_site").fetchone()[0]
    assert count == 1


def test_touching_one_file_reparses_only_that_file(conn, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(
        'from openai import OpenAI\n'
        "client = OpenAI()\n"
        'client.chat.completions.create(model="gpt-4-0613", messages=[])\n'
    )
    (tmp_path / "src" / "b.py").write_text(
        'from openai import OpenAI\n'
        "client = OpenAI()\n"
        'client.chat.completions.create(model="gpt-4-turbo", messages=[])\n'
    )

    incremental_index(conn, tmp_path, repo="acme/widgets")

    (tmp_path / "src" / "a.py").write_text(
        'from openai import OpenAI\n'
        "client = OpenAI()\n"
        'client.chat.completions.create(model="gpt-4o", messages=[])\n'
    )

    stats = incremental_index(conn, tmp_path, repo="acme/widgets")
    assert stats.parsed == 1
    assert stats.skipped == 1

    count = conn.execute("SELECT count(*) FROM call_site").fetchone()[0]
    assert count == 2  # replaced, not appended

    row = conn.execute(
        """
        SELECT s.value FROM call_site cs
        JOIN indexed_file f ON f.id = cs.indexed_file_id
        JOIN surface s ON s.id = cs.surface_id
        WHERE f.path = 'src/a.py'
        """
    ).fetchone()
    assert row[0] == "gpt-4o"


def test_deleted_file_removes_its_call_sites(conn, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(
        'from openai import OpenAI\n'
        "client = OpenAI()\n"
        'client.chat.completions.create(model="gpt-4-0613", messages=[])\n'
    )

    incremental_index(conn, tmp_path, repo="acme/widgets")
    (tmp_path / "src" / "a.py").unlink()

    stats = incremental_index(conn, tmp_path, repo="acme/widgets")
    assert stats.deleted == 1

    count = conn.execute("SELECT count(*) FROM call_site").fetchone()[0]
    assert count == 0

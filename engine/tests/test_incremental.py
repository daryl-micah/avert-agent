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
from avert.detect.events import fingerprint
from avert.detect.registry import load_events
from avert.index.incremental import incremental_index
from avert.join import impacted_call_sites

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


def test_model_lifecycle_join_is_definite_for_literal_and_possible_for_dynamic(conn, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "llm.py").write_text(
        'from openai import OpenAI\n'
        "client = OpenAI()\n"
        'client.chat.completions.create(model="gpt-4-0613", messages=[])\n'
        "client.chat.completions.create(model=model_name, messages=[])\n"
        'client.chat.completions.create(model="gpt-4o", messages=[])\n'
    )
    incremental_index(conn, tmp_path, repo="acme/widgets")
    event = next(event for event in load_events() if event.surface.value == "gpt-4-0613")
    event_id = db.upsert_change_event(conn, event, fingerprint=fingerprint(event))
    conn.commit()

    matches = impacted_call_sites(conn, event_id)

    assert [(match.line_start, match.match_kind) for match in matches] == [
        (3, "definite"),
        (4, "possible"),
    ]


def test_apply_migrations_is_idempotent(conn):
    assert db.apply_migrations(conn) == []
    names = {row[0] for row in conn.execute("SELECT name FROM schema_migration").fetchall()}
    assert "0001_init.sql" in names
    assert "0003_repository_installation.sql" in names


def test_inventory_status_comes_from_the_join(conn, tmp_path):
    from datetime import date

    from avert.inventory import build_inventory

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "llm.py").write_text(
        "from openai import OpenAI\n"
        "from anthropic import Anthropic\n"
        "client = OpenAI()\n"
        'client.chat.completions.create(model="gpt-4-0613", messages=[])\n'
        "client.chat.completions.create(model=chosen, messages=[])\n"
        'Anthropic().messages.create(model="claude-opus-4-8", messages=[])\n'
    )
    incremental_index(conn, tmp_path, repo="acme/widgets", github_installation_id=42)
    for event in load_events():
        db.upsert_change_event(conn, event, fingerprint=fingerprint(event))
    conn.commit()

    before = build_inventory(conn, today=date(2026, 9, 18))
    after = build_inventory(conn, today=date(2026, 12, 1))

    assert before.repositories == ["acme/widgets"]
    assert before.call_site_count == 3
    by_value = {(d.surface.value, d.value_binding): d for d in before.dependencies}
    literal = by_value[("gpt-4-0613", "literal")]
    assert literal.status == "retiring"
    assert str(literal.effective_at) == "2026-10-23"
    assert literal.replacement == "gpt-5.6-sol"
    assert by_value[(None, "dynamic")].status == "unknown"
    assert by_value[("claude-opus-4-8", "literal")].status == "current"
    assert before.attention_count == 1
    assert [d.status for d in before.dependencies] == ["retiring", "unknown", "current"]

    after_literal = {(d.surface.value, d.value_binding): d for d in after.dependencies}
    assert after_literal[("gpt-4-0613", "literal")].status == "retired"


def test_inventory_scopes_to_an_installation(conn, tmp_path):
    from avert.inventory import build_inventory

    for name, installation in (("a", 1), ("b", 2)):
        root = tmp_path / name
        (root / "src").mkdir(parents=True)
        (root / "src" / "llm.py").write_text(
            "from openai import OpenAI\n"
            'OpenAI().chat.completions.create(model="gpt-4o", messages=[])\n'
        )
        incremental_index(conn, root, repo=f"acme/{name}", github_installation_id=installation)

    everything = build_inventory(conn)
    scoped = build_inventory(conn, github_installation_id=2)

    assert everything.repositories == ["acme/a", "acme/b"]
    assert everything.call_site_count == 2
    assert scoped.repositories == ["acme/b"]
    assert scoped.call_site_count == 1
    assert scoped.dependencies[0].locations[0].repo == "acme/b"


def test_local_reindex_keeps_installation(conn, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "llm.py").write_text("from openai import OpenAI\n")
    incremental_index(conn, tmp_path, repo="acme/widgets", github_installation_id=7)
    incremental_index(conn, tmp_path, repo="acme/widgets")

    row = conn.execute("SELECT github_installation_id FROM repository").fetchone()
    assert row[0] == 7


def _seed_two_repositories(conn, tmp_path):
    for name, installation, body in (
        ("a", 1, 'client.chat.completions.create(model="gpt-4-0613", messages=[])\n'),
        ("b", 2, "client.chat.completions.create(model=chosen, messages=[])\n"),
    ):
        root = tmp_path / name
        (root / "src").mkdir(parents=True)
        (root / "src" / "llm.py").write_text("from openai import OpenAI\nclient = OpenAI()\n" + body)
        incremental_index(conn, root, repo=f"acme/{name}", github_installation_id=installation)
    for event in load_events():
        db.upsert_change_event(conn, event, fingerprint=fingerprint(event))
    conn.commit()


def test_impact_report_states_blast_radius_per_event(conn, tmp_path):
    from avert.impacts import build_impact_report

    _seed_two_repositories(conn, tmp_path)

    report = build_impact_report(conn)
    by_model = {impact.event.surface.value: impact for impact in report.impacts}

    assert len(report.impacts) == 10
    gpt4 = by_model["gpt-4-0613"]
    assert gpt4.blast_radius == "2 call sites in 2 files across 2 repositories (1 possible)"
    assert [(m.repo, m.match_kind) for m in gpt4.matches] == [
        ("acme/a", "definite"), ("acme/b", "possible"),
    ]
    assert by_model["claude-3-opus-20240229"].blast_radius == "no tracked call sites affected"

    scoped = build_impact_report(conn, github_installation_id=1)
    scoped_gpt4 = {i.event.surface.value: i for i in scoped.impacts}["gpt-4-0613"]
    assert [m.repo for m in scoped_gpt4.matches] == ["acme/a"]
    assert scoped_gpt4.blast_radius == "1 call site in 1 file across 1 repository"


def test_alerts_deliver_once_per_event_and_repository(conn, tmp_path):
    from avert.alerts import deliver_alerts

    _seed_two_repositories(conn, tmp_path)
    sent: list[tuple[str, dict]] = []

    first = deliver_alerts(conn, webhook_url="https://hooks.example/x", send=lambda u, p: sent.append((u, p)))
    second = deliver_alerts(conn, webhook_url="https://hooks.example/x", send=lambda u, p: sent.append((u, p)))

    assert (first.delivered, first.skipped) == (2, 0)
    assert (second.delivered, second.skipped) == (0, 2)
    assert len(sent) == 2
    url, payload = sent[0]
    assert url == "https://hooks.example/x"
    assert payload["repo"] == "acme/a"
    assert payload["replacement"] == "gpt-5.6-sol"
    assert payload["text"].startswith("[breaking] acme/a: gpt-4-0613 retires; migrate to gpt-5.6-sol. effective 2026-10-23.")
    assert "1 call site in 1 file across 1 repository. Migrate to gpt-5.6-sol." in payload["text"]


def test_failed_delivery_is_not_recorded(conn, tmp_path):
    from avert.alerts import deliver_alerts

    _seed_two_repositories(conn, tmp_path)

    def failing(url, payload):
        raise RuntimeError("webhook returned 500")

    with pytest.raises(RuntimeError):
        deliver_alerts(conn, webhook_url="https://hooks.example/x", send=failing)
    assert conn.execute("SELECT count(*) FROM alert_delivery").fetchone()[0] == 0

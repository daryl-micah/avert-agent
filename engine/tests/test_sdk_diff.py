from pathlib import Path

from avert.detect.sdk_diff.diff import diff_artifacts

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_diff"


def test_python_sdk_diff_normalizes_changed_openai_method():
    events = diff_artifacts(
        ecosystem="pypi", package="openai", from_path=FIXTURES / "python" / "from",
        to_path=FIXTURES / "python" / "to", from_version="1.0.0", to_version="2.0.0",
        source_url="https://example.test/openai",
    )

    assert len(events) == 1
    event = events[0]
    assert event.change_type == "type_changed"
    assert event.surface.provider == "openai"
    assert event.surface.resource == "chat.completions"
    assert event.severity == "breaking"


def test_typescript_sdk_diff_normalizes_changed_openai_method():
    events = diff_artifacts(
        ecosystem="npm", package="openai", from_path=FIXTURES / "typescript" / "from",
        to_path=FIXTURES / "typescript" / "to", from_version="1.0.0", to_version="2.0.0",
        source_url="https://example.test/openai",
    )

    assert len(events) == 1
    event = events[0]
    assert event.change_type == "type_changed"
    assert event.surface.provider == "openai"
    assert event.surface.resource == "chat.completions"
    assert event.severity == "breaking"


def test_unknown_package_is_rejected():
    try:
        diff_artifacts(
            ecosystem="pypi", package="unknown", from_path=FIXTURES / "python" / "from",
            to_path=FIXTURES / "python" / "to", from_version="1", to_version="2",
            source_url="https://example.test/unknown",
        )
    except ValueError as exc:
        assert "unsupported package" in str(exc)
    else:
        raise AssertionError("unknown package was accepted")

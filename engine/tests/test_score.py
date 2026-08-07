from avert.models.call_site_schema import CallSite
from avert.models.surface_id_schema import SurfaceID
from avert.score import Label, score


def _call_site(*, resource="chat.completions", value="gpt-4-0613", value_binding="literal", line=6):
    return CallSite(
        surface=SurfaceID(provider="openai", resource=resource, operation="create", field_path="model", value=value),
        repo="acme/widgets",
        commit_sha=None,
        file_path="src/llm.py",
        line_start=line,
        line_end=line,
        language="python",
        api_version=None,
        value_binding=value_binding,
        confidence=1.0,
        extractor="tree_sitter.python",
        file_content_hash="0" * 64,
    )


def test_unmatched_predictions_lower_per_bucket_precision():
    # One matched call site (line 6) plus one unmatched extra call site
    # (line 9) that no label expects — a real false positive.
    label = Label(
        file_path="src/llm.py",
        line=6,
        difficulty="typed_sdk",
        expect_detected=True,
        provider="openai",
        resource="chat.completions",
        operation="create",
        field_path="model",
        value="gpt-4-0613",
        value_binding="literal",
    )
    predictions = [_call_site(line=6), _call_site(line=9, value="gpt-4-turbo")]

    report = score([label], predictions)

    assert report.overall.precision == 0.5
    # Per-bucket precision must reflect the same false positive, not just
    # the overall total.
    assert report.by_language["python"].false_positives == 1
    assert report.by_language["python"].precision == 0.5
    assert report.by_value_binding["literal"].false_positives == 1
    assert report.by_value_binding["literal"].precision == 0.5

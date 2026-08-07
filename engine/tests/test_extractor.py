from avert.index.parse import extract_call_sites

PY_SOURCE = b"""
client = OpenAI()
anthropic_client = Anthropic()

def literal():
    return client.chat.completions.create(model="gpt-4-0613", messages=[])

def dynamic(model_name):
    return client.chat.completions.create(model=model_name, messages=[])

def absent():
    return client.chat.completions.create(messages=[])

def anthropic_call():
    return anthropic_client.messages.create(model="claude-3-opus-20240229", messages=[])

def untracked():
    return requests.get("https://example.com")
"""

TS_SOURCE = b"""
const client = new OpenAI();

async function literalCall() {
  return client.chat.completions.create({ model: "gpt-4-0613", messages: [] });
}

async function dynamicCall(modelName: string) {
  return client.chat.completions.create({ model: modelName, messages: [] });
}

async function templateLiteral() {
  return client.chat.completions.create({ model: `gpt-4-0613`, messages: [] });
}
"""

TSX_SOURCE = b"""
const client = new OpenAI();

function Widget() {
  async function onClick() {
    await client.chat.completions.create({ model: "gpt-4-0613", messages: [] });
  }
  return <button onClick={onClick}>Go</button>;
}
"""


def _by_line(sites, line):
    return next(s for s in sites if s.line_start == line)


def test_python_literal_dynamic_absent_and_untracked():
    sites = extract_call_sites(
        file_path="src/llm.py", language="python", source=PY_SOURCE,
        repo="acme/widgets", commit_sha="deadbeef",
    )
    assert len(sites) == 4

    literal = _by_line(sites, 6)
    assert literal.value_binding == "literal"
    assert literal.surface.value == "gpt-4-0613"
    assert literal.surface.provider == "openai"

    dynamic = _by_line(sites, 9)
    assert dynamic.value_binding == "dynamic"
    assert dynamic.surface.value is None

    absent = _by_line(sites, 12)
    assert absent.value_binding == "absent"
    assert absent.surface.value is None

    anthropic_call = _by_line(sites, 15)
    assert anthropic_call.surface.provider == "anthropic"
    assert anthropic_call.surface.resource == "messages"
    assert anthropic_call.value_binding == "literal"
    assert anthropic_call.surface.value == "claude-3-opus-20240229"


def test_typescript_literal_dynamic_and_template():
    sites = extract_call_sites(
        file_path="src/llm.ts", language="typescript", source=TS_SOURCE,
        repo="acme/widgets", commit_sha=None,
    )
    assert len(sites) == 3

    literal = _by_line(sites, 5)
    assert literal.value_binding == "literal"
    assert literal.surface.value == "gpt-4-0613"

    dynamic = _by_line(sites, 9)
    assert dynamic.value_binding == "dynamic"

    template = _by_line(sites, 13)
    assert template.value_binding == "literal"
    assert template.surface.value == "gpt-4-0613"


def test_tsx_files_use_the_tsx_grammar():
    # The plain TypeScript grammar can't parse JSX; using it on a .tsx file
    # either errors or silently drops every call site inside the component.
    sites = extract_call_sites(
        file_path="src/Widget.tsx", language="typescript", source=TSX_SOURCE,
        repo="acme/widgets", commit_sha=None,
    )
    assert len(sites) == 1
    assert sites[0].value_binding == "literal"
    assert sites[0].surface.value == "gpt-4-0613"


def test_all_sites_carry_file_hash_and_extractor_tag():
    sites = extract_call_sites(
        file_path="src/llm.py", language="python", source=PY_SOURCE,
        repo="acme/widgets", commit_sha=None,
    )
    assert all(len(s.file_content_hash) == 64 for s in sites)
    assert all(s.extractor == "tree_sitter.python" for s in sites)
    # chat.completions is a distinctive multi-segment match -> full confidence.
    # messages.create (anthropic) is a generic single-word resource that
    # collides with unrelated SDKs (e.g. Twilio) -> lower confidence.
    openai_sites = [s for s in sites if s.surface.provider == "openai"]
    anthropic_sites = [s for s in sites if s.surface.provider == "anthropic"]
    assert openai_sites and all(s.confidence == 1.0 for s in openai_sites)
    assert anthropic_sites and all(s.confidence == 0.6 for s in anthropic_sites)

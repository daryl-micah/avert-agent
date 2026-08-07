from avert import vocabulary


def test_matches_openai_chat_completions():
    m = vocabulary.match_callee("client.chat.completions.create")
    assert m is not None
    assert m.provider == "openai"
    assert m.resource == "chat.completions"
    assert m.operation == "create"


def test_matches_anthropic_messages():
    m = vocabulary.match_callee("anthropic_client.messages.create")
    assert m is not None
    assert m.provider == "anthropic"
    assert m.resource == "messages"
    assert m.operation == "create"


def test_no_match_for_untracked_call():
    assert vocabulary.match_callee("requests.get") is None


def test_no_match_for_unknown_operation():
    assert vocabulary.match_callee("client.chat.completions.delete") is None

import litellm
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic


def via_litellm_prefixed(messages):
    # Provider is carried by the model string, not the callee.
    return litellm.completion(model="anthropic/claude-3-opus-20240229", messages=messages)


def via_litellm_bare(messages):
    # litellm resolves a bare name through its own routing table.
    return litellm.completion(model="gpt-4-0613", messages=messages)


def via_litellm_dynamic(model, messages):
    # Provider unknown until runtime.
    return litellm.completion(model=model, messages=messages)


openai_chat = ChatOpenAI(model="gpt-4-0613")
anthropic_chat = ChatAnthropic(model="claude-3-opus-20240229")

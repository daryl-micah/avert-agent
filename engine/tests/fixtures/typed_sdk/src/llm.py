from openai import OpenAI
from anthropic import Anthropic

client = OpenAI()
anthropic_client = Anthropic()


def call_literal():
    return client.chat.completions.create(model="gpt-4-0613", messages=[])


def call_dynamic(model_name):
    return client.chat.completions.create(model=model_name, messages=[])


def call_absent():
    return client.chat.completions.create(messages=[])


def call_anthropic():
    return anthropic_client.messages.create(model="claude-3-opus-20240229", messages=[])


def call_untracked():
    return requests.get("https://example.com")

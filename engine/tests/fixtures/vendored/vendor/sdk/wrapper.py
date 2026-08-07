"""Vendored openai wrapper — checked in by a third-party dependency, not
written by us. A real call site, but deliberately out of scope for the
indexer (candidates.EXCLUDE_GLOBS skips vendor/**), same as node_modules."""
from openai import OpenAI

client = OpenAI()


def call_openai():
    return client.chat.completions.create(model="gpt-4-0613", messages=[])

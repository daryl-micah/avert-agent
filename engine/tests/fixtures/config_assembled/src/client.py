"""Talks to the openai chat completions endpoint, built from config."""
import requests

import config


def call_openai():
    url = f"{config.OPENAI_BASE_URL}/chat/completions"
    return requests.post(url, json={"model": config.DEFAULT_MODEL, "messages": []})

import requests


def call_openai():
    return requests.post(
        "https://api.openai.com/v1/chat/completions",
        json={"model": "gpt-4-0613", "messages": []},
        headers={"Authorization": "Bearer sk-..."},
    )

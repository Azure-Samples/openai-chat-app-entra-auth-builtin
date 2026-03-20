import os
from unittest import mock

import pytest
import pytest_asyncio
from azure.keyvault.secrets.aio import SecretClient

import quartapp

from . import mock_cred


@pytest.fixture
def mock_openai_responses(monkeypatch):
    class MockResponseEvent:
        """Simulates a Responses API streaming event."""

        def __init__(self, event_type, delta=None):
            self.type = event_type
            self.delta = delta

    class AsyncResponseIterator:
        def __init__(self, answer: str):
            self.event_index = 0
            self.events = []
            answer_deltas = answer.split(" ")
            for i, word in enumerate(answer_deltas):
                if i > 0:
                    word = " " + word
                self.events.append(MockResponseEvent("response.output_text.delta", delta=word))
            self.events.append(MockResponseEvent("response.completed"))

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.event_index < len(self.events):
                event = self.events[self.event_index]
                self.event_index += 1
                return event
            else:
                raise StopAsyncIteration

    async def mock_acreate(*args, **kwargs):
        last_message = kwargs.get("input", [])[-1]["content"]
        if last_message == "What is the capital of France?":
            return AsyncResponseIterator("The capital of France is Paris.")
        elif last_message == "What is the capital of Germany?":
            return AsyncResponseIterator("The capital of Germany is Berlin.")
        else:
            raise ValueError(f"Unexpected message: {last_message}")

    monkeypatch.setattr("openai.resources.responses.AsyncResponses.create", mock_acreate)


@pytest.fixture
def mock_defaultazurecredential(monkeypatch):
    monkeypatch.setattr("azure.identity.aio.DefaultAzureCredential", mock_cred.MockAzureCredential)
    monkeypatch.setattr("azure.identity.aio.ManagedIdentityCredential", mock_cred.MockAzureCredential)


@pytest.fixture
def mock_keyvault_secretclient(monkeypatch):
    monkeypatch.setenv("AZURE_KEY_VAULT_NAME", "my_key_vault")
    monkeypatch.setenv("OPENAICOM_API_KEY_SECRET_NAME", "my_secret_name")

    async def get_secret(*args, **kwargs):
        if args[1] == "my_secret_name":
            return mock_cred.MockKeyVaultSecret("mysecret")
        raise Exception(f"Unexpected secret name: {args[1]}")

    monkeypatch.setattr(SecretClient, "get_secret", get_secret)


@pytest_asyncio.fixture
async def client(monkeypatch, mock_openai_responses, mock_defaultazurecredential):
    with mock.patch.dict(os.environ, clear=True):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "test-openai-service.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_CHATGPT_DEPLOYMENT", "gpt-5.2")

        quart_app = quartapp.create_app()

        async with quart_app.test_app() as test_app:
            quart_app.config.update({"TESTING": True})

            yield test_app.test_client()

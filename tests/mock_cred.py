import azure.core.credentials_async


class MockAzureCredential(azure.core.credentials_async.AsyncTokenCredential):
    def __init__(self, *args, **kwargs):
        pass


class MockKeyVaultSecret:
    def __init__(self, value):
        self.value = value


class MockKeyVaultSecretClient:
    async def get_secret(self, secret_name):
        return MockKeyVaultSecret("mysecret")

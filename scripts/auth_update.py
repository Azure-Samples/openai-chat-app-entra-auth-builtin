import asyncio
import logging
import os

from auth_common import get_application, update_azd_env, load_azd_env
from azure.identity.aio import AzureDeveloperCliCredential
from msgraph import GraphServiceClient
from msgraph.generated.models.application import Application
from msgraph.generated.models.public_client_application import PublicClientApplication
from msgraph.generated.models.web_application import WebApplication
from rich.logging import RichHandler


logging.basicConfig(
    level=logging.WARNING, format="%(message)s", handlers=[RichHandler(rich_tracebacks=True, log_time_format="")]
)
logger = logging.getLogger("authsetup")
logger.setLevel(logging.INFO)


async def main():
    tenantId = os.getenv("AZURE_AUTH_TENANT_ID", None)
    credential = AzureDeveloperCliCredential(tenant_id=tenantId)

    scopes = ["https://graph.microsoft.com/.default"]
    graph_client = GraphServiceClient(credentials=credential, scopes=scopes)

    uri = os.getenv("SERVICE_ACA_URI", "no-uri")
    if uri == "no-uri":
        logger.info("No URI set, not updating authentication...")
        exit(0)
    client_app_id = os.getenv("AZURE_CLIENT_APP_ID", None)
    if client_app_id:
        client_object_id = await get_application(graph_client, client_app_id)
        if client_object_id:
            logger.info("Updating client application redirect URIs...")
            # Redirect URIs need to be relative to the deployed application
            app = Application(
                public_client=PublicClientApplication(redirect_uris=[]),
                web=WebApplication(
                    redirect_uris=[
                        "http://localhost:50505/.auth/login/aad/callback",
                        f"{uri}/.auth/login/aad/callback",
                    ]
                ),
            )
            await graph_client.applications.by_application_id(client_object_id).patch(app)
            logger.info(f"Application update for client app id {client_app_id} complete.")

    logger.info("Clearing secrets as they should now be stored in Key Vault...")
    update_azd_env("OPENAICOM_API_KEY", '""')
    update_azd_env("AZURE_CLIENT_APP_SECRET", '""')
    logger.info("Post-provisioning script complete.")


if __name__ == "__main__":
    load_azd_env()
    asyncio.run(main())

import asyncio
import datetime
import logging
import os
import random
import sys

from auth_common import (
    add_application_owner,
    create_or_update_application_with_secret,
    get_current_user,
    get_microsoft_graph_service_principal,
    get_tenant_details,
    update_azd_env,
    load_azd_env,
)

from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import AzureDeveloperCliCredential, ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph_beta import GraphServiceClient as GraphServiceClientBeta
from msgraph_beta.generated.models.external_users_self_service_sign_up_events_flow import (
    ExternalUsersSelfServiceSignUpEventsFlow,
)
from msgraph_beta.generated.identity.authentication_events_flows.authentication_events_flows_request_builder import (
    AuthenticationEventsFlowsRequestBuilder,
)
from msgraph_beta.generated.models.built_in_identity_provider import BuiltInIdentityProvider
from msgraph_beta.generated.models.on_user_create_start_external_users_self_service_sign_up import (
    OnUserCreateStartExternalUsersSelfServiceSignUp,
)
from msgraph_beta.generated.models.on_interactive_auth_flow_start_external_users_self_service_sign_up import (
    OnInteractiveAuthFlowStartExternalUsersSelfServiceSignUp,
)
from msgraph_beta.generated.models.on_authentication_method_load_start_external_users_self_service_sign_up import (
    OnAuthenticationMethodLoadStartExternalUsersSelfServiceSignUp,
)
from msgraph_beta.generated.models.on_attribute_collection_external_users_self_service_sign_up import (
    OnAttributeCollectionExternalUsersSelfServiceSignUp,
)
from msgraph_beta.generated.models.identity_user_flow_attribute import IdentityUserFlowAttribute
from msgraph_beta.generated.models.authentication_condition_application import AuthenticationConditionApplication
from msgraph_beta.generated.models.authentication_attribute_collection_page import AuthenticationAttributeCollectionPage
from msgraph_beta.generated.models.authentication_attribute_collection_page_view_configuration import (
    AuthenticationAttributeCollectionPageViewConfiguration,
)
from msgraph_beta.generated.models.authentication_attribute_collection_input_configuration import (
    AuthenticationAttributeCollectionInputConfiguration,
)
from msgraph_beta.generated.models.authentication_attribute_collection_input_type import (
    AuthenticationAttributeCollectionInputType,
)
from msgraph_beta.generated.models.user_type import UserType
from msgraph.generated.models.o_auth2_permission_grant import OAuth2PermissionGrant
from msgraph_beta.generated.oauth2_permission_grants.oauth2_permission_grants_request_builder import (
    Oauth2PermissionGrantsRequestBuilder,
)
from msgraph.generated.models.application import Application
from msgraph.generated.models.implicit_grant_settings import ImplicitGrantSettings
from msgraph.generated.models.required_resource_access import RequiredResourceAccess
from msgraph.generated.models.resource_access import ResourceAccess
from msgraph.generated.models.web_application import WebApplication
from kiota_abstractions.base_request_configuration import RequestConfiguration
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.WARNING, format="%(message)s", handlers=[RichHandler(rich_tracebacks=True, log_time_format="")]
)
logger = logging.getLogger("authsetup")
logger.setLevel(logging.INFO)


def random_app_identifier():
    rand = random.Random()
    rand.seed(datetime.datetime.now().timestamp())
    return rand.randint(1000, 100000)


async def get_permission_grant(
    graph_client_beta: GraphServiceClient, obj_id: str, resource_id: str, scope: str
) -> str | None:
    query_params = Oauth2PermissionGrantsRequestBuilder.Oauth2PermissionGrantsRequestBuilderGetQueryParameters(
        filter=f"clientId eq '{obj_id}' and resourceId eq '{resource_id}'"
    )
    request_configuration = RequestConfiguration(query_parameters=query_params)
    result = await graph_client_beta.oauth2_permission_grants.get(request_configuration=request_configuration)
    for permission in result.value:
        if permission.scope == scope:
            return permission.id
    return None


async def create_permission_grant(graph_client: GraphServiceClient, obj_id: str, resource_id: str, scope: str) -> str:
    """https://learn.microsoft.com/en-us/graph/api/oauth2permissiongrant-post"""
    request_body = OAuth2PermissionGrant(
        client_id=obj_id,
        consent_type="AllPrincipals",
        resource_id=resource_id,
        scope=scope,
    )

    result = await graph_client.oauth2_permission_grants.post(request_body)
    return result.id


async def get_or_create_permission_grant(graph_client: GraphServiceClient, sp_id: str, graph_sp_id: str):
    logger.info(
        f"Possibly creating permission grant to authorize client SP {sp_id} to access Graph SP {graph_sp_id}..."
    )
    permission_scopes = " ".join(["User.Read", "offline_access", "openid", "profile"])
    grant_id = await get_permission_grant(graph_client, sp_id, graph_sp_id, permission_scopes)
    if grant_id:
        logger.info("Permission grant already exists, not creating new one")
    else:
        logger.info("Creating permission grant")
        await create_permission_grant(graph_client, sp_id, graph_sp_id, permission_scopes)


def client_app(identifier: int) -> Application:
    return Application(
        display_name=f"ChatGPT Sample Client App {identifier}",
        sign_in_audience="AzureADMyOrg",
        web=WebApplication(
            redirect_uris=["http://localhost:50505/.auth/login/aad/callback"],
            implicit_grant_settings=ImplicitGrantSettings(enable_id_token_issuance=True),
        ),
        required_resource_access=[
            RequiredResourceAccess(
                resource_app_id="00000003-0000-0000-c000-000000000000",
                resource_access=[
                    ResourceAccess(id="e1fe6dd8-ba31-4d61-89e7-88639da4683d", type="Scope"),  # Graph User.Read
                    ResourceAccess(id="7427e0e9-2fba-42fe-b0c0-848c9e6a8182", type="Scope"),  # offline_access
                    ResourceAccess(id="37f7f235-527c-4136-accd-4a02d197296e", type="Scope"),  # openid
                    ResourceAccess(id="14dad69e-099b-42c9-810b-d002981feec1", type="Scope"),  # profile
                ],
            )
        ],
    )


def permission_scopes() -> str:
    return " ".join(["User.Read", "offline_access", "openid", "profile"])


def client_userflow(identifier: int):
    """https://learn.microsoft.com/graph/api/resources/externalusersselfservicesignupeventsflow"""
    return ExternalUsersSelfServiceSignUpEventsFlow(
        display_name=f"ChatGPT Sample User Flow {identifier}",
        description=f"ChatGPT Sample User Flow {identifier}",
        priority=500,
        on_user_create_start=OnUserCreateStartExternalUsersSelfServiceSignUp(user_type_to_create=UserType.Member),
        on_attribute_collection=OnAttributeCollectionExternalUsersSelfServiceSignUp(
            attributes=[
                IdentityUserFlowAttribute(
                    display_name="Email Address",
                    data_type="string",
                    description="Email address of the user",
                    id="email",
                    user_flow_attribute_type="builtIn",
                ),
                IdentityUserFlowAttribute(
                    display_name="Display Name",
                    data_type="string",
                    description="Display Name of the User.",
                    id="displayName",
                    user_flow_attribute_type="builtIn",
                ),
            ],
            attribute_collection_page=AuthenticationAttributeCollectionPage(
                views=[
                    AuthenticationAttributeCollectionPageViewConfiguration(
                        inputs=[
                            AuthenticationAttributeCollectionInputConfiguration(
                                attribute="email",
                                required=True,
                                label="Email Address",
                                write_to_directory=True,
                                input_type=AuthenticationAttributeCollectionInputType("text"),
                                hidden=True,
                                editable=False,
                                validation_reg_ex="^[a-zA-Z0-9.!#$%&amp;&#8217;'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\\.[a-zA-Z0-9-]+)*$",  # noqa: E501
                            ),
                            AuthenticationAttributeCollectionInputConfiguration(
                                attribute="displayName",
                                required=True,
                                label="Display Name",
                                write_to_directory=True,
                                input_type=AuthenticationAttributeCollectionInputType("text"),
                                hidden=False,
                                editable=True,
                                validation_reg_ex="^.*",
                            ),
                        ]
                    )
                ]
            ),
        ),
        on_interactive_auth_flow_start=OnInteractiveAuthFlowStartExternalUsersSelfServiceSignUp(
            is_sign_up_allowed=True,
        ),
        on_authentication_method_load_start=OnAuthenticationMethodLoadStartExternalUsersSelfServiceSignUp(
            identity_providers=[
                BuiltInIdentityProvider(
                    display_name="Email One Time Passcode",
                    identity_provider_type="EmailOTP",
                    id="EmailOtpSignup-OAUTH",
                )
            ]
        ),
    )


async def get_userflow(graph_client_beta: GraphServiceClientBeta, app_id: str) -> str | None:
    """https://learn.microsoft.com/graph/api/resources/externalusersselfservicesignupeventsflow"""

    query_params = AuthenticationEventsFlowsRequestBuilder.AuthenticationEventsFlowsRequestBuilderGetQueryParameters(
        filter=f"conditions/applications/includeApplications/any(a:a/appId eq '{app_id}')"
    )
    request_configuration = RequestConfiguration(
        query_parameters=query_params,
    )
    result = await graph_client_beta.identity.authentication_events_flows.get(
        request_configuration=request_configuration
    )
    if result.value:
        return result.value[0].id
    return None


async def create_userflow(
    graph_client_beta: GraphServiceClientBeta, client_flow: ExternalUsersSelfServiceSignUpEventsFlow
) -> str:
    """https://learn.microsoft.com/graph/api/resources/externalusersselfservicesignupeventsflow"""
    result = await graph_client_beta.identity.authentication_events_flows.post(client_flow)
    return result.id


async def get_or_create_userflow(
    graph_client_beta: GraphServiceClientBeta, app_id: str, client_userflow: ExternalUsersSelfServiceSignUpEventsFlow
) -> str:
    logger.info(f"Possibly creating user flow for {app_id}...")
    userflow_id = await get_userflow(graph_client_beta, app_id)
    if userflow_id:
        logger.info("Found an existing user flow associated with client app")
    else:
        logger.info("Creating new user flow")
        userflow_id = await create_userflow(graph_client_beta, client_userflow)
    return userflow_id


async def userflow_has_app(graph_client_beta: GraphServiceClientBeta, userflow_id: str, app_id: str) -> bool:
    """https://learn.microsoft.com/graph/api/authenticationconditionsapplications-list-includeapplications"""
    result = await graph_client_beta.identity.authentication_events_flows.by_authentication_events_flow_id(
        userflow_id
    ).conditions.applications.include_applications.get()
    app_ids = [item.app_id for item in result.value]
    return app_id in app_ids


async def add_app_to_userflow(graph_client_beta: GraphServiceClientBeta, userflow_id: str, app_id: str):
    """https://learn.microsoft.com/graph/api/authenticationconditionsapplications-post-includeapplications"""
    request_body = AuthenticationConditionApplication(app_id=app_id)
    await graph_client_beta.identity.authentication_events_flows.by_authentication_events_flow_id(
        userflow_id
    ).conditions.applications.include_applications.post(request_body)


async def get_or_create_userflow_app(graph_client_beta: GraphServiceClientBeta, userflow_id: str, app_id: str) -> bool:
    logger.info(f"Possibly setting up association between userflow {userflow_id} and client app {app_id}...")
    flow_app_exists = await userflow_has_app(graph_client_beta, userflow_id, app_id)
    if flow_app_exists:
        logger.info("User flow is already associated with client app.")
    else:
        logger.info("Adding user flow to client app.")
        await add_app_to_userflow(graph_client_beta, userflow_id, app_id)


def get_credential(tenant_id: str) -> AsyncTokenCredential:
    client_id = os.getenv("AZURE_AUTH_EXTID_APP_ID", None)
    if client_id is None:
        logger.info(f"Using Azd CLI Credential for tenant_id {tenant_id}")
        return AzureDeveloperCliCredential(tenant_id=tenant_id)
    client_secret = os.getenv("AZURE_AUTH_EXTID_APP_SECRET", None)
    logger.info(f"Using Client Secret Credential for client ID {client_id}")
    return ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)


async def main():
    tenant_id = os.getenv("AZURE_AUTH_TENANT_ID", None)
    logger.info("Setting up authentication for tenant %s" % tenant_id)
    try:
        credential = get_credential(tenant_id)
        scopes = ["https://graph.microsoft.com/.default"]
        graph_client = GraphServiceClient(credentials=credential, scopes=scopes)
        graph_client_beta = GraphServiceClientBeta(credentials=credential, scopes=scopes)
    except Exception as e:
        logger.error("Error occurred: %s", e)
        sys.exit(1)
    try:
        (tenant_type, _) = await get_tenant_details(AzureDeveloperCliCredential(tenant_id=tenant_id), tenant_id)
        logger.info(f"Detected a tenant of type: {tenant_type}")
        if tenant_type == "CIAM":
            current_user = os.getenv("AZURE_AUTH_EXTID_APP_OWNER", None)
        else:
            current_user = await get_current_user(graph_client)

        app_identifier = os.getenv("AZURE_CLIENT_IDENTIFIER", random_app_identifier())
        update_azd_env("AZURE_CLIENT_IDENTIFIER", app_identifier)
        (app_obj_id, app_id, sp_id) = await create_or_update_application_with_secret(
            graph_client,
            app_id_env_var="AZURE_CLIENT_APP_ID",
            app_secret_env_var="AZURE_CLIENT_APP_SECRET",
            request_app=client_app(app_identifier),
        )

        if tenant_type == "CIAM":
            graph_sp_id = await get_microsoft_graph_service_principal(graph_client)
            await get_or_create_permission_grant(graph_client, sp_id, graph_sp_id)

            if current_user is not None:
                await add_application_owner(graph_client, app_obj_id, current_user)

            userflow_id = await get_or_create_userflow(graph_client_beta, app_id, client_userflow(app_identifier))
            await get_or_create_userflow_app(graph_client_beta, userflow_id, app_id)
    except Exception as e:
        logger.error("Error occurred: %s", e)
        sys.exit(1)
    finally:
        await credential.close()
    logger.info("Pre-provisioning script complete.")


if __name__ == "__main__":
    load_azd_env()
    asyncio.run(main())

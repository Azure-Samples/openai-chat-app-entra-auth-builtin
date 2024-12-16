
# Customize the deployment

Follow these steps to customize the provisioning and deployment of the Azure resources.

The general way to customize a deploy is to set azd environment variables using the `azd env set` command, *before* running the `azd up` command.

Once you've set the desired azd environment variables, return to the [deployment steps](../README.md#deployment).

* [Use existing resource group](#use-existing-resource-group)
* [Use existing Azure OpenAI resource](#use-existing-azure-openai-resource)
* [Use existing OpenAI.com OpenAI resource](#use-existing-openaicom-openai-resource)

## Reduce the Azure OpenAI quota

This application requests 30K TPM (tokens-per-minute) for the Azure OpenAI chat model.
If your account does not have that much capacity available, you can reduce the quota requested by the application.

For example, to request 8K TPM:

```shell
azd env set AZURE_OPENAI_DEPLOYMENT_CAPACITY 8
```

## Use existing resource group

1. Run `azd env set AZURE_RESOURCE_GROUP {Name of existing resource group}`
1. Run `azd env set AZURE_LOCATION {Location of existing resource group}`

## Use existing Azure OpenAI resource

If you already have an OpenAI resource and would like to re-use it, run `azd env set` to specify the values for the existing OpenAI resource.

```shell
azd env set AZURE_OPENAI_RESOURCE {name of OpenAI resource}
azd env set AZURE_OPENAI_RESOURCE_GROUP {name of resource group that it's inside}
azd env set AZURE_OPENAI_RESOURCE_GROUP_LOCATION {location for that group}
azd env set AZURE_OPENAI_SKU_NAME {name of the SKU, defaults to "S0"}
```

## Use existing OpenAI.com OpenAI resource

If you already have an OpenAI.com API key and would like to re-use it:

1. Disable the creation of an Azure OpenAI resource:

    ```shell
    azd env set DEPLOY_AZURE_OPENAI false
    ```

1. Specify the value for the existing OpenAI.com API key:

    ```shell
    azd env set OPENAICOM_API_KEY {your OpenAI.com API key}
    ```

The key will be stored in Key Vault when you run `azd up`, and fetched from Key Vault inside the application code.
You must run `azd up` to store the key in Key Vault before running the application.

## Deploying with the free trial

By default, this project deploys to Azure Container Apps, using a remote build process that builds the Docker image in the cloud. Unfortunately, free trial accounts cannot use that remote build process.

To disable remote builds, follow these steps:

1. Make sure you have docker installed by running `docker --version` in your terminal.
2. Comment out or delete `remoteBuild: true` in azure.yaml

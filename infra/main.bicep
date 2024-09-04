targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name which is used to generate a short unique hash for each resource')
param name string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Flag to decide where to create OpenAI role for current user')
param createRoleForUser bool = true

param acaExists bool = false

param deployAzureOpenAi bool = true

@description('Running on GitHub Actions?')
param runningOnGh bool = false

param keyVaultName string = ''

param openAiResourceName string = ''
param openAiResourceGroupName string = ''

// https://learn.microsoft.com/azure/ai-services/openai/concepts/models#standard-deployment-model-availability
@description('Location for the OpenAI resource')
@allowed([ 'eastus', 'swedencentral' ])
@metadata({
  azd: {
    type: 'location'
  }
})
param openAiResourceLocation string
param openAiDeploymentName string = 'chatgpt'
param openAiSkuName string = ''
param openAiDeploymentCapacity int // Set in main.parameters.json
param openAiApiVersion string = ''

var openAiConfig = {
  modelName: 'gpt-4o-mini'
  modelVersion: '2024-07-18'
  deploymentName: !empty(openAiDeploymentName) ? openAiDeploymentName : 'chatgpt'
  deploymentCapacity: openAiDeploymentCapacity != 0 ? openAiDeploymentCapacity : 30
}

@secure()
param openAiComAPIKey string = ''
param openAiComAPIKeySecretName string = 'openai-com-api-key'

param authClientId string = ''
@secure()
param authClientSecret string = ''
param authClientSecretName string = 'AZURE-AUTH-CLIENT-SECRET'
param authTenantId string
param loginEndpoint string = ''
param tenantId string = tenant().tenantId
var tenantIdForAuth = !empty(authTenantId) ? authTenantId : tenantId

var resourceToken = toLower(uniqueString(subscription().id, name, location))
var tags = { 'azd-env-name': name }

resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: '${name}-rg'
  location: location
  tags: tags
}

resource openAiResourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' existing = if (!empty(openAiResourceGroupName)) {
  name: !empty(openAiResourceGroupName) ? openAiResourceGroupName : resourceGroup.name
}

var prefix = '${name}-${resourceToken}'

module openAi 'core/ai/cognitiveservices.bicep' = if (deployAzureOpenAi) {
  name: 'openai'
  scope: openAiResourceGroup
  params: {
    name: !empty(openAiResourceName) ? openAiResourceName : '${resourceToken}-cog'
    tags: tags
    location: openAiResourceLocation
    sku: {
      name: !empty(openAiSkuName) ? openAiSkuName : 'S0'
    }
    disableLocalAuth: true
    deployments: [
      {
        name: openAiConfig.deploymentName
        model: {
          format: 'OpenAI'
          name: openAiConfig.modelName
          version: openAiConfig.modelVersion
        }
        sku: {
          name: 'Standard'
          capacity: openAiConfig.deploymentCapacity
        }
      }
    ]
  }
}

module logAnalyticsWorkspace 'core/monitor/loganalytics.bicep' = {
  name: 'loganalytics'
  scope: resourceGroup
  params: {
    name: '${prefix}-loganalytics'
    location: location
    tags: tags
  }
}

// Container apps host (including container registry)
module containerApps 'core/host/container-apps.bicep' = {
  name: 'container-apps'
  scope: resourceGroup
  params: {
    name: 'app'
    location: location
    tags: tags
    containerAppsEnvironmentName: '${prefix}-containerapps-env'
    containerRegistryName: '${replace(prefix, '-', '')}registry'
    logAnalyticsWorkspaceName: logAnalyticsWorkspace.outputs.name
  }
}

module keyVault 'core/security/keyvault.bicep' = {
  name: 'keyvault'
  scope: resourceGroup
  params: {
    name: !empty(keyVaultName) ? keyVaultName : '${replace(take(prefix, 17), '-', '')}-vault'
    location: location
    principalId: principalId
  }
}

module userKeyVaultAccess 'core/security/role.bicep' = {
  name: 'user-keyvault-access'
  scope: resourceGroup
  params: {
    principalId: principalId
    principalType: runningOnGh ? 'ServicePrincipal' : 'User'
    roleDefinitionId: '00482a5a-887f-4fb3-b363-3b7fe8e74483'
  }
}

module backendKeyVaultAccess 'core/security/role.bicep' = {
  name: 'backend-keyvault-access'
  scope: resourceGroup
  params: {
    principalId: acaIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: '00482a5a-887f-4fb3-b363-3b7fe8e74483'
  }
}


module openAiComAPIKeyStorage 'core/security/keyvault-secret.bicep' = if (!empty(openAiComAPIKey)) {
  name: 'openai-key-secret'
  scope: resourceGroup
  params: {
    keyVaultName: keyVault.outputs.name
    name: openAiComAPIKeySecretName
    secretValue: openAiComAPIKey
  }
}


module authClientSecretStorage 'core/security/keyvault-secret.bicep' = if (!empty(authClientSecret)) {
    name: 'secrets'
    scope: resourceGroup
    params: {
      keyVaultName: keyVault.outputs.name
      name: authClientSecretName
      secretValue: authClientSecret
    }
  }

module acaIdentity 'core/security/identity.bicep' = {
    name: 'aca-identity'
    scope: resourceGroup
    params: {
      name: '${prefix}-id-aca'
    }
}

// Container app frontend
module aca 'aca.bicep' = {
  name: 'aca'
  scope: resourceGroup
  params: {
    name: replace('${take(prefix,19)}-ca', '--', '-')
    location: location
    tags: tags
    identityName: acaIdentity.outputs.name
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    openAiDeploymentName: deployAzureOpenAi ? openAiConfig.deploymentName : ''
    openAiEndpoint: deployAzureOpenAi ? openAi.outputs.endpoint : ''
    openAiApiVersion: deployAzureOpenAi ? openAiApiVersion : ''
    openAiComAPIKeySecretName: openAiComAPIKeySecretName
    exists: acaExists
    authClientId: authClientId
    authClientSecretName: authClientSecretName
    authTenantId: tenantIdForAuth
    authLoginEndpoint: loginEndpoint
    azureKeyVaultName: keyVault.outputs.name
  }
  dependsOn: [authClientSecretStorage, backendKeyVaultAccess]
}


module openAiRoleUser 'core/security/role.bicep' = if (createRoleForUser && deployAzureOpenAi) {
  scope: openAiResourceGroup
  name: 'openai-role-user'
  params: {
    principalId: principalId
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    principalType: 'User'
  }
}


module openAiRoleBackend 'core/security/role.bicep' = if (deployAzureOpenAi) {
  scope: openAiResourceGroup
  name: 'openai-role-backend'
  params: {
    principalId: acaIdentity.outputs.principalId
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    principalType: 'ServicePrincipal'
  }
}


output AZURE_LOCATION string = location

output AZURE_OPENAI_CHATGPT_DEPLOYMENT string = deployAzureOpenAi ? openAiConfig.deploymentName : ''
output AZURE_OPENAI_API_VERSION string = deployAzureOpenAi ? openAiApiVersion : ''
output AZURE_OPENAI_ENDPOINT string = deployAzureOpenAi ? openAi.outputs.endpoint : ''
output AZURE_OPENAI_RESOURCE string = deployAzureOpenAi ? openAi.outputs.name : ''
output AZURE_OPENAI_RESOURCE_GROUP string = deployAzureOpenAi ? openAiResourceGroup.name : ''
output AZURE_OPENAI_RESOURCE_GROUP_LOCATION string = deployAzureOpenAi ? openAiResourceGroup.location : ''
output OPENAICOM_API_KEY_SECRET_NAME string = openAiComAPIKeySecretName
output OPENAI_MODEL_NAME string = openAiConfig.modelName

output SERVICE_ACA_IDENTITY_PRINCIPAL_ID string = acaIdentity.outputs.principalId
output SERVICE_ACA_NAME string = aca.outputs.name
output SERVICE_ACA_URI string = aca.outputs.uri
output SERVICE_ACA_IMAGE_NAME string = aca.outputs.imageName

output AZURE_CONTAINER_ENVIRONMENT_NAME string = containerApps.outputs.environmentName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApps.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApps.outputs.registryName

output AZURE_KEY_VAULT_NAME string = keyVault.outputs.name

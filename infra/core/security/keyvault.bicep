metadata description = 'Creates an Azure Key Vault.'
param name string
param location string = resourceGroup().location
param tags object = {}

param principalId string = ''

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
  }
}

output endpoint string = keyVault.properties.vaultUri
output name string = keyVault.name

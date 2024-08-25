param name string
param location string = resourceGroup().location

resource acaIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
}

output name string = acaIdentity.name
output principalId string = acaIdentity.properties.principalId

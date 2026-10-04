// Deploy only after owner approval. No Always Ready, registry, database server,
// private endpoint or paid telemetry workspace. Application code verifies Entra.
targetScope = 'resourceGroup'

param location string = 'swedencentral'
param appName string
@minLength(3)
@maxLength(24)
param storageName string
param apiAudience string
param operatorPrincipalId string
param tenantId string = tenant().tenantId
@description('Enable only with permission to assign Storage data roles. Dedicated-account server credentials are the fallback.')
param useManagedIdentity bool = true

var tags = { project: 'rare-disease-atlas' }

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: !useManagedIdentity
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {}
}
resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'function-packages'
  properties: { publicAccess: 'None' }
}
resource intakeContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'atlas-mcp'
  properties: { publicAccess: 'None' }
}
resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: '${appName}-plan'
  location: location
  tags: tags
  sku: { name: 'FC1', tier: 'FlexConsumption' }
  properties: { reserved: true }
}
var storageConnection = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
var storageSettings = useManagedIdentity ? [
  { name: 'AzureWebJobsStorage__accountName', value: storage.name }
  { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
] : [
  { name: 'AzureWebJobsStorage', value: storageConnection }
  { name: 'ATLAS_STORAGE_CONNECTION_STRING', value: storageConnection }
  { name: 'MCP_DEPLOY_STORAGE', value: storageConnection }
]
resource app 'Microsoft.Web/sites@2024-04-01' = {
  name: appName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}${deploymentContainer.name}'
          authentication: useManagedIdentity ? { type: 'SystemAssignedIdentity' } : {
            type: 'StorageAccountConnectionString'
            storageAccountConnectionStringName: 'MCP_DEPLOY_STORAGE'
          }
        }
      }
      runtime: { name: 'python', version: '3.11' }
      scaleAndConcurrency: {
        instanceMemoryMB: 512
        maximumInstanceCount: 40 // Flex's documented minimum maximum; no reserved instances.
        triggers: { http: { perInstanceConcurrency: 4 } }
      }
    }
    siteConfig: {
      minTlsVersion: '1.2'
      appSettings: concat(storageSettings, [
        { name: 'AzureWebJobsFeatureFlags', value: 'EnableMcpCustomHandlerPreview' }
        { name: 'PYTHONPATH', value: '/home/site/wwwroot/.python_packages/lib/site-packages' }
        { name: 'ATLAS_STORAGE_ACCOUNT', value: storage.name }
        { name: 'ATLAS_TENANT_ID', value: tenantId }
        { name: 'ATLAS_API_AUDIENCE', value: apiAudience }
        { name: 'ATLAS_PUBLIC_URL', value: 'https://${appName}.azurewebsites.net/mcp' }
      ])
    }
  }
}
var dataRoles = [
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3' // Storage Table Data Contributor
]
resource appRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in dataRoles: if (useManagedIdentity) {
  name: guid(storage.id, app.id, role)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
  }
}]
resource operatorRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in dataRoles: if (useManagedIdentity) {
  name: guid(storage.id, operatorPrincipalId, role)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
    principalId: operatorPrincipalId
    principalType: 'User'
  }
}]
output mcpUrl string = 'https://${app.properties.defaultHostName}/mcp'
output accountName string = storage.name

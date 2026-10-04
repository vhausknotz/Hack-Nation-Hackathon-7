# Dedicated MCP controls. The website and shared model resource are never targeted.
# Status: powershell -File tools/azure_mcp.ps1 status
# Stop compute: powershell -File tools/azure_mcp.ps1 stop
# Remove app/storage after backing up wanted contributions:
# powershell -File tools/azure_mcp.ps1 remove -ConfirmRemove
param(
    [ValidateSet('status','stop','start','remove')][string]$Action = 'status',
    [switch]$ConfirmRemove
)
$ErrorActionPreference = 'Stop'
Import-Module Az.Accounts
$atlasContext = Get-AzContext
if (-not $atlasContext) { throw 'Not signed in. Run Connect-AzAccount first.' }
$atlasGroupName = 'rare-disease-atlas-mcp'
$atlasScope = '/subscriptions/' + $atlasContext.Subscription.Id + '/resourceGroups/' + $atlasGroupName
$atlasGroupReply = Invoke-AzRestMethod -Method GET -Path ($atlasScope + '?api-version=2021-04-01')
if ($atlasGroupReply.StatusCode -eq 404) {
    Write-Host 'MCP: NOT PROVISIONED in the current subscription.'
    exit 0
}
if ($atlasGroupReply.StatusCode -ne 200) { throw ('Cannot read MCP group: HTTP ' + $atlasGroupReply.StatusCode) }
$atlasGroup = $atlasGroupReply.Content | ConvertFrom-Json
if ($atlasGroup.tags.project -ne 'rare-disease-atlas' -or $atlasGroup.tags.component -ne 'mcp') {
    throw 'Refusing operation: the dedicated group does not have the expected project/component tags.'
}
$atlasReply = Invoke-AzRestMethod -Method GET -Path ($atlasScope + '/resources?api-version=2021-04-01')
if ($atlasReply.StatusCode -ne 200) { throw ('Cannot list MCP resources: HTTP '+$atlasReply.StatusCode) }
$atlasResources = @(($atlasReply.Content | ConvertFrom-Json).value)
$atlasFunctions = @($atlasResources | Where-Object { $_.type -eq 'Microsoft.Web/sites' })
if ($Action -eq 'remove') {
    if (-not $ConfirmRemove) {
        Write-Host 'This permanently removes MCP app/storage, including cloud submissions and archives.'
        Write-Host 'Back up wanted data, then re-run with -ConfirmRemove. Website/models are separate.'
        exit 1
    }
    $atlasDeleted = Invoke-AzRestMethod -Method DELETE -Path ($atlasScope + '?api-version=2021-04-01')
    if ($atlasDeleted.StatusCode -notin @(200,202,204)) { throw ('Removal failed: HTTP '+$atlasDeleted.StatusCode) }
    Write-Host 'MCP removal requested. Re-run status until the group is gone; Azure deletion is asynchronous.'
    Write-Host 'Entra application registration is separate, has no compute charge, and remains available for reuse.'
    exit 0
}
foreach ($atlasFunction in $atlasFunctions) {
    if ($Action -in @('stop','start')) {
        $atlasChanged = Invoke-AzRestMethod -Method POST -Path ($atlasFunction.id+'/'+$Action+'?api-version=2024-04-01')
        if ($atlasChanged.StatusCode -notin @(200,202,204)) { throw ($Action+' failed: HTTP '+$atlasChanged.StatusCode) }
    }
    $atlasDetail = Invoke-AzRestMethod -Method GET -Path ($atlasFunction.id+'?api-version=2024-04-01')
    if ($atlasDetail.StatusCode -ne 200) { throw ('Cannot verify function state: HTTP '+$atlasDetail.StatusCode) }
    $atlasApp = $atlasDetail.Content | ConvertFrom-Json
    Write-Host ('MCP app: '+$atlasApp.properties.state+' | '+$atlasApp.name)
    Write-Host ('Endpoint: https://'+$atlasApp.properties.defaultHostName+'/mcp')
}
if (-not $atlasFunctions.Count) { Write-Host 'MCP app: NOT DEPLOYED. The dedicated resource group exists.' }
foreach ($atlasStorage in @($atlasResources | Where-Object { $_.type -eq 'Microsoft.Storage/storageAccounts' })) {
    Write-Host ('Storage retained: '+$atlasStorage.name+' (storage/request charges continue when the app is stopped)')
}
Write-Host ('Portal: https://portal.azure.com/#resource'+$atlasScope+'/overview')
Write-Host 'Application limits: 1,000 tool calls/day globally, 250/contributor; these are not an Azure dollar cap.'
Write-Host 'Stop: powershell -File tools/azure_mcp.ps1 stop'
Write-Host 'Remove: powershell -File tools/azure_mcp.ps1 remove -ConfirmRemove'

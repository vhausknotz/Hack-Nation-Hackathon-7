# Lists every Azure resource of this project (tag project=rare-disease-atlas) with its pricing tier,
# plus the shared Azure OpenAI resource the pipeline calls. Run:  powershell -File tools/azure_status.ps1
Import-Module Az.Accounts
$ctx = Get-AzContext
if (-not $ctx) { Write-Host "Not logged in. Run Connect-AzAccount first."; exit 1 }
$sub = $ctx.Subscription.Id
Write-Host "Subscription: $($ctx.Subscription.Name)`n"

$resp = Invoke-AzRestMethod -Method GET -Path "/subscriptions/$sub/resources?`$filter=tagName eq 'project' and tagValue eq 'rare-disease-atlas'&api-version=2021-04-01"
$items = ($resp.Content | ConvertFrom-Json).value
if (-not $items) { Write-Host "No project resources are running. Nothing costs money here." }
foreach ($r in $items) {
    $detail = Invoke-AzRestMethod -Method GET -Path "$($r.id)?api-version=2022-09-01"
    $sku = (($detail.Content | ConvertFrom-Json).sku.name)
    $rg = ($r.id -split "/")[4]
    $cost = if ($sku -eq "Free") { "free" } else { "PAID tier: check Cost Management" }
    Write-Host ("ON  {0,-28} {1,-34} tier={2,-10} {3}  (resource group: {4})" -f $r.name, $r.type, $sku, $cost, $rg)
    if ($r.type -eq "Microsoft.Web/staticSites") {
        Write-Host ("    url: https://{0}" -f (($detail.Content | ConvertFrom-Json).properties.defaultHostname))
    }
}

Write-Host "`nShared model resource (pay per use, only costs money while the pipeline or agents call it):"
$ai = Invoke-AzRestMethod -Method GET -Path "/subscriptions/$sub/providers/Microsoft.CognitiveServices/accounts?api-version=2024-10-01"
foreach ($a in (($ai.Content | ConvertFrom-Json).value | Where-Object { $_.name -eq "valiOpenAI" })) {
    Write-Host ("    {0} ({1}) - billed per token used" -f $a.name, $a.location)
}
Write-Host "`nTo switch the project off: powershell -File tools/azure_off.ps1"
Write-Host "For accurate MCP app state and its separate controls: powershell -File tools/azure_mcp.ps1 status"

# Switches the project off: deletes every resource group tagged project=rare-disease-atlas
# (the website and anything else created for this project). Asks before deleting.
# It does NOT touch the shared Azure OpenAI resource (valiOpenAI), which is pay-per-use and idle when unused.
# Run:  powershell -File tools/azure_off.ps1
Import-Module Az.Accounts
$sub = (Get-AzContext).Subscription.Id
$resp = Invoke-AzRestMethod -Method GET -Path "/subscriptions/$sub/resourcegroups?`$filter=tagName eq 'project' and tagValue eq 'rare-disease-atlas'&api-version=2021-04-01"
$groups = ($resp.Content | ConvertFrom-Json).value
if (-not $groups) { Write-Host "Nothing to switch off: no project resource groups exist."; exit 0 }
foreach ($g in $groups) { Write-Host "Will delete resource group: $($g.name) (and everything in it)" }
$answer = Read-Host "Type DELETE to switch the project off"
if ($answer -ne "DELETE") { Write-Host "Cancelled. Nothing was changed."; exit 0 }
foreach ($g in $groups) {
    $r = Invoke-AzRestMethod -Method DELETE -Path "/subscriptions/$sub/resourcegroups/$($g.name)?api-version=2021-04-01"
    Write-Host "Deleting $($g.name): HTTP $($r.StatusCode) (Azure finishes this in the background)"
}
Write-Host "Done. Run tools/azure_status.ps1 in a few minutes to confirm nothing is left."

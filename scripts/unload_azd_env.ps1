$envValues = azd env get-values
$envValues.Split("`n") | ForEach-Object {
    $keyValue = $_.Split('=')
    $key = $keyValue[0]
    $value = $keyValue[1] -replace '^"|"$', ''
    Remove-Item Env:$key
}

Write-Host "Unloaded azd env variables from current environment."

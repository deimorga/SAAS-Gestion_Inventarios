$headers = @{
    "Authorization" = "Bearer mk_secret_JtK77Q4_oWujlft2RzzSC9iTIeSRD74aV4FlI4aiCzWDnYGk"
    "Content-Type"  = "application/json"
}

$baseUrl = "http://localhost:8002/v1"

function Post-Api {
    param([string]$endpoint, [hashtable]$body)
    $jsonBody = $body | ConvertTo-Json -Depth 5
    try {
        $res = Invoke-RestMethod -Uri "$baseUrl$endpoint" -Method Post -Headers $headers -Body $jsonBody
        return $res
    } catch {
        $errResponse = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($errResponse)
        $errText = $reader.ReadToEnd()
        if ($_.Exception.Response.StatusCode -eq 409) {
            Write-Host "Ya existe en $endpoint"
        } else {
            Write-Host "Error en $endpoint : $errText"
        }
    }
}

Write-Host "Creando Productos..."
$prod1 = @{
    sku = "LUB-5W30-01"
    name = "Aceite Sintético 5W-30 (Litro)"
    category_id = "4398143a-a910-4a4e-8eae-6cf549f95cef" # Lubricantes
    base_uom = "Litro"
}
Post-Api -endpoint "/products" -body $prod1

$prod2 = @{
    sku = "FIL-ACE-01"
    name = "Filtro de Aceite Universal"
    category_id = "d131dd58-229c-4c75-bad5-dcf3b27a87d7" # Filtros
    base_uom = "Unidad"
}
Post-Api -endpoint "/products" -body $prod2

Write-Host "Creando Bodega..."
$wh = @{
    code = "B-PRINCIPAL"
    name = "Bodega Principal"
    type = "STORE"
    is_sellable = $true
}
Post-Api -endpoint "/warehouses" -body $wh

Write-Host "Hecho."

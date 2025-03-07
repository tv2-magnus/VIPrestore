# Read version from version.txt and trim whitespace
$VERSION = Get-Content -Path "version.txt" -Raw
$VERSION = $VERSION.Trim()

# Construct the installer path based on your directory structure
$INSTALLER_DIR = "C:\Users\meo\VIPrestore\dist\VIPrestore $VERSION"
$INSTALLER_PATH = "$INSTALLER_DIR\VIPrestore-$VERSION-Setup.exe"

# Check if the version is valid
if ([string]::IsNullOrEmpty($VERSION)) {
    Write-Error "Error: Could not read version from version.txt"
    exit 1
}

# Check if the installer exists at the expected path
if (-not (Test-Path $INSTALLER_PATH)) {
    Write-Warning "Installer not found at expected path: $INSTALLER_PATH"
    Write-Host "Trying to find the installer automatically..."
    
    # Try to find the installer using a more flexible pattern
    $POSSIBLE_INSTALLERS = Get-ChildItem -Path "C:\Users\meo\VIPrestore\dist" -Recurse -File -Filter "VIPrestore-$VERSION-Setup*.exe"
    
    if ($POSSIBLE_INSTALLERS.Count -gt 0) {
        $INSTALLER_PATH = $POSSIBLE_INSTALLERS[0].FullName
        Write-Host "Found installer at: $INSTALLER_PATH"
    } else {
        Write-Error "Could not find installer. Please check the path."
        exit 1
    }
}

Write-Host "Creating GitHub release v$VERSION with installer: $INSTALLER_PATH"

# Create the GitHub release with version from version.txt
gh release create "v$VERSION" --generate-notes --title "VIPrestore v$VERSION" "$INSTALLER_PATH"

# Check if the command succeeded
if ($LASTEXITCODE -eq 0) {
    Write-Host "Release v$VERSION created successfully!" -ForegroundColor Green
} else {
    Write-Host "Failed to create release. Make sure you're authenticated with GitHub." -ForegroundColor Red
}
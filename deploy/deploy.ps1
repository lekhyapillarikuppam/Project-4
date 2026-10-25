# Redeploy the Tripwise backend to the Azure VM (008 DEP-FR-01). Run from the repo root in PowerShell:
#   .\deploy\deploy.ps1
# Ships the committed backend and data/curated (git archive HEAD), reinstalls requirements, restarts the service
# and checks /health over HTTPS. Secrets stay in /etc/tripwise.env on the VM (never in the repo).
$ErrorActionPreference = "Stop"
$Key = "$env:USERPROFILE\Downloads\audiobook-key.pem"
$Vm = "azureuser@20.219.52.200"
$Url = "https://lekhya-audiobook.centralindia.cloudapp.azure.com/tripwise/health"
$Tar = Join-Path $env:TEMP "tripwise.tgz"
git archive --format=tar.gz -o $Tar HEAD backend data/curated
scp -i $Key $Tar "${Vm}:/tmp/tripwise.tgz"
ssh -i $Key $Vm @'
set -e
sudo systemctl stop tripwise-api
sudo find /opt/tripwise/backend -mindepth 1 -maxdepth 1 ! -name .venv -exec rm -rf {} +
sudo rm -rf /opt/tripwise/data
sudo tar -xzf /tmp/tripwise.tgz -C /opt/tripwise && rm /tmp/tripwise.tgz
sudo /opt/tripwise/backend/.venv/bin/pip install -q -r /opt/tripwise/backend/requirements.txt
sudo chown -R tripwise:tripwise /opt/tripwise
sudo systemctl start tripwise-api
'@
Start-Sleep -Seconds 12
Invoke-RestMethod $Url

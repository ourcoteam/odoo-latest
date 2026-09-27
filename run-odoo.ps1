# Run Odoo server on Windows
Write-Host "🚀 Starting Odoo 19 Server..."
Write-Host "Database User: odoo"
Write-Host "Database Host: localhost:5432"
Write-Host "Odoo Server: http://localhost:8069"
Write-Host ""

python odoo-bin -c odoo.conf --http-port=8069

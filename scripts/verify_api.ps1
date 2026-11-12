# Run while API is up
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/v1/diagnosis/diagnose -ContentType "application/json" -Body '{"host_key":"cattle","organism_hint":"livestock","danger_signs_present":true}'

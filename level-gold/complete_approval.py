import json
import shutil
from pathlib import Path

# Move plan file to Done
shutil.move('AI_Employee_Vault/Plans/FOLLOWUP_ODOO_19ccf296.md', 'AI_Employee_Vault/Done/')

# Log completion
log_entry = {
    'timestamp': '2026-03-09T13:35:00+00:00',
    'action': 'plan_completed',
    'actor': 'fte-approve',
    'source': 'Plans/FOLLOWUP_ODOO_19ccf296.md',
    'destination': 'Done/FOLLOWUP_ODOO_19ccf296.md',
    'result': 'success',
    'details': 'Follow-up sequence complete - Day 14 final email sent to rinmatsouka369@gmail.com'
}

with open('AI_Employee_Vault/Logs/2026-03-09.json', 'a') as f:
    f.write(json.dumps(log_entry) + '\n')

print('✅ Plan moved to Done and logged')

"""
Dedicated CRM sync worker module
"""
from workers.webhooks import sync_call_to_crm

# Re-export for cleaner imports
__all__ = ['sync_call_to_crm']

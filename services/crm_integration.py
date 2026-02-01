from abc import ABC, abstractmethod
import json

class CRMAdapter(ABC):
    @abstractmethod
    def sync_data(self, data: dict, config: dict) -> str:
        pass

class GoogleSheetsAdapter(CRMAdapter):
    def sync_data(self, data: dict, config: dict) -> str:
        # Simulation of the original Google Sheets logic
        sheet_name = config.get("sheet_name")
        return f"✅ SUCCESS: Row appended to Google Sheet [{sheet_name}] (Simulated)"

class SalesforceAdapter(CRMAdapter):
    def sync_data(self, data: dict, config: dict) -> str:
        # Simulation of Salesforce API interaction
        # In prod: simple_salesforce.Salesforce(...).create('Lead', ...)
        domain = config.get("sf_domain")
        return f"✅ SUCCESS: Lead created in Salesforce [{domain}] with ID: SF-{hash(data['prospect_name']) % 10000}"

class HubSpotAdapter(CRMAdapter):
    def sync_data(self, data: dict, config: dict) -> str:
        # Simulation of HubSpot API
        portal_id = config.get("portal_id")
        return f"✅ SUCCESS: Contact updated in HubSpot Portal [{portal_id}]"

class CRMFactory:
    @staticmethod
    def get_adapter(crm_type: str) -> CRMAdapter:
        if crm_type == "salesforce":
            return SalesforceAdapter()
        elif crm_type == "hubspot":
            return HubSpotAdapter()
        else:
            return GoogleSheetsAdapter()
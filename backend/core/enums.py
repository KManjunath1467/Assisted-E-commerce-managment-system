"""Shared enumeration types used across the agents, tools, schemas, and API layers.

Severity, CampaignStatus, and Channel are re-exported from domains.common
(the MCP server's single source of truth) so that the same enum types are used
when deserialising MCP tool responses.
"""

from enum import Enum


class AgentDomain(str, Enum):
    SALES = "sales"
    INVENTORY = "inventory"
    MARKETING = "marketing"
    CUSTOMER_SUPPORT = "customer_support"


class ActionType(str, Enum):
    RESTOCK = "restock"
    RUN_DISCOUNT = "run_discount"
    PAUSE_CAMPAIGN = "pause_campaign"
    RESUME_CAMPAIGN = "resume_campaign"
    CREATE_SUPPORT_TICKET = "create_support_ticket"


class ActionStatus(str, Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class IncidentStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"

MAX_RETRIES: int = 3
REORDER_POINT: int = 30  # low-stock threshold (units)
DATA_START_DATE: str = "2026-03-10"  # earliest date in the seeded dataset

DISCOUNT_PCT: int = 15  # default discount percentage for demand stimulation
REVENUE_DEVIATION_THRESHOLD: float = -20.0  # % deviation that triggers a discount recommendation
ROAS_THRESHOLD: float = 1.5  # ROAS below this is considered underperforming
TICKET_CHANGE_THRESHOLD: float = 30.0  # % ticket volume increase that triggers escalation
REFUND_RATE_THRESHOLD: float = 0.08  # refund rate above this triggers escalation

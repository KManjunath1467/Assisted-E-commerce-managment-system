// ─── Enums ─────────────────────────────────────────────────────────────────

export type AgentDomain =
  | "sales"
  | "inventory"
  | "marketing"
  | "customer_support";

export type Severity = "low" | "medium" | "high" | "critical";

export type ActionType =
  | "restock"
  | "run_discount"
  | "pause_campaign"
  | "resume_campaign"
  | "create_support_ticket";

export type ActionStatus =
  | "pending_approval"
  | "approved"
  | "rejected"
  | "executed";

export type CampaignStatus = "active" | "paused" | "ended" | "scheduled";

export type IncidentStatus = "open" | "resolved";

export type Channel = "email" | "social" | "search" | "display" | "affiliate";

// ─── Common ────────────────────────────────────────────────────────────────

/** Both fields are ISO 8601 UTC datetime strings. */
export interface TimeRange {
  start: string;
  end: string;
}

export interface Anomaly {
  metric: string;
  expected: number;
  actual: number;
  deviation_pct: number;
  severity: Severity;
}

export interface ProductRef {
  product_id: string;
  name: string;
  category: string | null;
}

// ─── Sales ─────────────────────────────────────────────────────────────────

export interface ProductRevenue {
  product: ProductRef;
  revenue: number;
}

export interface SalesMetrics {
  total_revenue: number;
  order_count: number;
  avg_order_value: number;
  top_products: ProductRevenue[];
  by_region: Record<string, number>;
}

export interface SalesAnalysis {
  kind: "sales";
  period: TimeRange;
  metrics: SalesMetrics;
  anomalies: Anomaly[];
  insights: string[];
  comparison_period: SalesMetrics | null;
}

// ─── Inventory ─────────────────────────────────────────────────────────────

export interface StockLevel {
  product: ProductRef;
  quantity: number;
  unit_price: number | null;
  reorder_point: number | null;
  days_until_stockout: number | null;
  is_out_of_stock: boolean;
}

export interface InventoryAnalysis {
  kind: "inventory";
  stock_levels: StockLevel[];
  stockout_missed_views: ProductRef[];
  estimated_sales_impact: number | null;
  insights: string[];
}

// ─── Marketing ─────────────────────────────────────────────────────────────

export interface CampaignMetrics {
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  roas: number;
}

export interface Campaign {
  campaign_id: string;
  name: string;
  channel: Channel;
  status: CampaignStatus;
  current_period: CampaignMetrics;
  previous_period: CampaignMetrics | null;
  /** ISO date string YYYY-MM-DD */
  start_date: string;
  end_date: string | null;
}

export interface MarketingAnalysis {
  kind: "marketing";
  campaigns: Campaign[];
  underperforming: Campaign[];
  missed_promotions: string[];
  worst_channel: Channel | null;
  insights: string[];
}

// ─── Customer Support ──────────────────────────────────────────────────────

export interface CustomerComplaint {
  category: string;
  count: number;
  sample_texts: string[];
  /** -1.0 to +1.0 */
  sentiment_score: number;
}

export interface CustomerSupportAnalysis {
  kind: "customer_support";
  period_tickets: number;
  previous_period_tickets: number | null;
  tickets_change_pct: number | null;
  /** 0 – 1 */
  refund_rate: number;
  /** 0 – 1 */
  return_rate: number;
  negative_reviews: number;
  common_issues: CustomerComplaint[];
  insights: string[];
}

// ─── Discriminated union over all domain-level analysis shapes ─────────────

export type DomainAnalysisData =
  | SalesAnalysis
  | InventoryAnalysis
  | MarketingAnalysis
  | CustomerSupportAnalysis;

// ─── Analysis ──────────────────────────────────────────────────────────────

export interface CrossDomainCorrelation {
  description: string;
  evidence: string[];
}

export interface DomainFinding {
  domain: AgentDomain;
  severity: Severity;
  data: DomainAnalysisData;
}

export interface RootCauseAnalysis {
  is_incomplete: boolean;
  primary_cause: string | string[];
  contributing_factors: string[];
  correlations: CrossDomainCorrelation[];
  evidence: string[];
  /** 0.0 – 1.0 */
  confidence: number;
}

export interface ReflectionResult {
  is_complete: boolean;
  needs_more_data: boolean;
  missing_domains: AgentDomain[];
  /** 0.0 – 1.0 */
  confidence: number;
  action_required: boolean;
  issues: Record<string, string>;
}

// ─── Actions ───────────────────────────────────────────────────────────────

export interface RecommendedAction {
  action_type: ActionType;
  description: string;
  rationale: string;
  requires_approval: boolean;
  targets: string[];
  parameters: Record<string, unknown> | null;
}

/** Request body sent to POST /api/v1/actions/{id}/approve */
export interface ActionApprovalPayload {
  approved: boolean;
  approved_by: string | null;
  notes: string | null;
  thread_id: string | null;
}

export interface ActionExecutionResult {
  action_type: ActionType;
  status: ActionStatus;
  message: string;
  executed_at: string | null;
}

// ─── Outputs ───────────────────────────────────────────────────────────────

export interface OperationsReport {
  query: string;
  thread_id: string | null;
  incident_id: string | null;
  recommendations: RecommendedAction[];
  summary: string;
  requires_human_approval: boolean;
  generated_at: string;
}

// ─── Query ─────────────────────────────────────────────────────────────────

export interface QueryRequest {
  query: string;
  thread_id: string | null;
  time_range: TimeRange | null;
}

// ─── Pending action (from GET /api/v1/actions/pending) ────────────────────

export interface PendingAction {
  id: string;
  incident_id: string;
  action_type: ActionType;
  description: string;
  status: ActionStatus;
  created_at: string;
  executed_at: string | null;
  thread_id: string | null;
}

// ─── Incident (from GET /api/v1/incidents) ────────────────────────────────

export interface Incident {
  id: string;
  summary: string | null;
  status: "open" | "resolved";
  created_at: string;
  resolved_at: string | null;
  signals: Record<string, unknown> | null;
  resolution_summary: string | null;
  actions: PendingAction[];
}

// ─── API response from POST /api/v1/query ──────────────────────────────────

export interface QueryCompleteResponse {
  status: "complete";
  thread_id: string;
  report: OperationsReport;
  pending_actions: null;
}

export interface QueryPendingResponse {
  status: "pending_approval";
  thread_id: string;
  report: null;
  pending_actions: PendingAction[];
}

export type QueryResponse = QueryCompleteResponse | QueryPendingResponse;

// ─── Chat message discriminated union ─────────────────────────────────────

export interface UserMessage {
  id: string;
  type: "user";
  text: string;
  timestamp: string;
}

export interface ReportMessage {
  id: string;
  type: "report";
  report: OperationsReport;
  thread_id: string;
  timestamp: string;
}

export interface PendingApprovalMessage {
  id: string;
  type: "pending_approval";
  actions: PendingAction[];
  thread_id: string;
  timestamp: string;
  /** Map of actionId → result, populated as actions are resolved */
  resolvedActions: Record<string, ActionExecutionResult>;
  /** True when loaded from thread history — disables approve/reject buttons */
  is_historical?: boolean;
}

export interface ErrorMessage {
  id: string;
  type: "error";
  text: string;
  timestamp: string;
}

export type ChatMessage =
  | UserMessage
  | ReportMessage
  | PendingApprovalMessage
  | ErrorMessage
  | StreamingMessage;

/** Shown while the backend SSE stream is in progress. */
export interface StreamingMessage {
  id: string;
  type: "streaming";
  /** The node currently executing (replaces previous, never stacks). */
  currentNode: string | null;
  /** Accumulated streamed text from token events. */
  streamedText: string;
  timestamp: string;
}

// ─── Thread sidebar ────────────────────────────────────────────────────────

export interface ThreadSummary {
  thread_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ThreadMessageItem {
  id: string;
  role: "user" | "assistant";
  content: Record<string, unknown>;
  created_at: string;
}

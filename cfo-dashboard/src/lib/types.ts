export interface User {
  id: string
  email: string
  name: string
  language: 'en' | 'ar'
  timezone: string
  status: 'active' | 'invited' | 'disabled'
  created_at: string
}

export interface Company {
  id: string
  name: string
  legal_name: string | null
  country_code: string
  base_currency: string
  fiscal_year_start: number
  timezone: string
  tax_number: string | null
  created_at: string
}

export interface CompanyMembership {
  membership_id: string
  company_id: string
  company_name: string
  role: 'OWNER' | 'ADMIN' | 'ACCOUNTANT' | 'APPROVER' | 'VIEWER'
}

export interface Account {
  id: string
  company_id: string
  code: string
  name_en: string
  name_ar: string | null
  type: 'asset' | 'liability' | 'equity' | 'revenue' | 'expense'
  subtype: string
  currency: string | null
  parent_account_id: string | null
  is_payment_account: boolean
  is_system: boolean
  is_active: boolean
  created_at: string
}

export interface InboxItem {
  id: string
  company_id: string
  source: 'web_text' | 'web_receipt' | 'telegram' | 'api' | 'email'
  content_type: 'text' | 'image' | 'document'
  original_text: string | null
  detected_language: string
  status: 'received' | 'queued' | 'processing' | 'review_required' | 'completed' | 'extracted' | 'failed' | 'archived'
  error_code: string | null
  error_message: string | null
  created_at: string
  processed_at: string | null
  duplicate_status: 'unchecked' | 'unique' | 'likely_duplicate' | 'exact_duplicate'
  duplicate_reason: string | null
}

export interface Document {
  id: string
  company_id: string
  inbox_item_id: string | null
  original_name: string
  mime_type: string
  size_bytes: number
  document_type: string
  upload_status: string
  created_at: string
}

export interface Vendor {
  id: string
  company_id: string
  name: string
  normalized_name: string
  email: string | null
  phone: string | null
  tax_number: string | null
  country_code: string | null
  default_expense_account: string | null
  default_currency: string | null
  is_active: boolean
  created_at: string
}

export interface DraftTransaction {
  id: string
  company_id: string
  inbox_item_id: string | null
  document_id: string | null
  type: 'expense' | 'income' | 'transfer'
  amount: number
  tax_amount: number
  currency: string
  transaction_date: string
  description: string
  vendor_id: string | null
  category_account_id: string | null
  payment_account_id: string | null
  reference_number: string | null
  status: string
  ai_confidence: number | null
  created_by: string | null
  approved_by: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface JournalEntry {
  id: string
  company_id: string
  entry_number: string
  entry_date: string
  description: string
  source_type: string
  source_id: string | null
  status: string
  currency: string
  exchange_rate: number
  posted_by: string | null
  posted_at: string | null
  reversed_entry_id: string | null
  created_at: string
  lines: JournalLine[]
}

export interface JournalLine {
  id: string
  account_id: string
  description: string | null
  debit: number
  credit: number
  currency: string
  base_debit: number
  base_credit: number
}

export interface Budget {
  id: string
  company_id: string
  name: string
  period_type: 'monthly' | 'quarterly' | 'yearly'
  start_date: string
  end_date: string
  currency: string
  status: string
  created_by: string
  created_at: string
  lines: BudgetLine[]
}

export interface BudgetLine {
  id: string
  account_id: string
  planned_amount: number
  alert_percentage: number
}

export interface Notification {
  id: string
  company_id: string
  user_id: string | null
  channel: 'in_app' | 'telegram' | 'email'
  type: string
  title: string
  message: string
  entity_type: string | null
  entity_id: string | null
  status: string
  sent_at: string | null
  read_at: string | null
  created_at: string
}

export interface ApprovalRequest {
  id: string
  company_id: string
  entity_type: string
  entity_id: string
  requested_by: string | null
  assigned_to: string | null
  status: string
  comment: string | null
  resolved_by: string | null
  resolved_at: string | null
  created_at: string
}

export interface ExchangeRate {
  id: string
  base_currency: string
  quote_currency: string
  rate: number
  rate_date: string
  source: string
  created_at: string
}

export interface DashboardData {
  base_currency: string
  monthly_income: number
  monthly_expenses: number
  net_cash_flow: number
  pending_approvals: number
  recent_transactions: Record<string, unknown>[]
  budget_warnings: Record<string, unknown>[]
}

export interface PnLData {
  base_currency: string
  period: string
  revenue: Record<string, unknown>[]
  expenses: Record<string, unknown>[]
  net_income: number
}

export interface CashFlowData {
  base_currency: string
  period: string
  operating: number
  investing: number
  financing: number
  net: number
  monthly_data: Record<string, unknown>[]
}

export interface BalanceSheetData {
  base_currency: string
  as_of: string
  assets: Record<string, unknown>[]
  liabilities: Record<string, unknown>[]
  equity: Record<string, unknown>[]
  total_assets: number
  total_liabilities: number
  total_equity: number
}

export interface ExpenseByCategoryData {
  base_currency: string
  period: string
  categories: Record<string, unknown>[]
  total: number
}

export interface VendorReportData {
  period: string
  vendors: Record<string, unknown>[]
  total: number
}

export interface BudgetVsActualData {
  period: string
  items: Record<string, unknown>[]
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface TelegramStatus {
  connected: boolean
  bot_username: string | null
  chat_id: number | null
  status: string | null
  pairing_code?: string | null
  pairing_link?: string | null
  pairing_expires_at?: string | null
}

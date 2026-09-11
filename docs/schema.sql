-- Canonical SQLite-compatible schema. CSV files remain the Stage 2 interchange format.
CREATE TABLE vendors (
  vendor_id TEXT PRIMARY KEY,
  vendor_name TEXT NOT NULL,
  category TEXT NOT NULL,
  vendor_since DATE NOT NULL,
  payment_terms_days INTEGER NOT NULL CHECK (payment_terms_days > 0),
  status TEXT NOT NULL CHECK (status IN ('Active', 'Inactive', 'Blocked'))
);

CREATE TABLE purchase_orders (
  po_line_id TEXT PRIMARY KEY,
  po_id TEXT NOT NULL,
  vendor_id TEXT NOT NULL REFERENCES vendors(vendor_id),
  po_date DATE NOT NULL,
  item_id TEXT NOT NULL,
  ordered_quantity REAL NOT NULL CHECK (ordered_quantity > 0),
  unit_price REAL NOT NULL CHECK (unit_price >= 0),
  tax_rate REAL NOT NULL CHECK (tax_rate BETWEEN 0 AND 1),
  currency TEXT NOT NULL
);
CREATE INDEX idx_purchase_orders_po_id ON purchase_orders(po_id);

CREATE TABLE goods_receipts (
  receipt_line_id TEXT PRIMARY KEY,
  receipt_id TEXT NOT NULL,
  po_id TEXT NOT NULL,
  po_line_id TEXT NOT NULL REFERENCES purchase_orders(po_line_id),
  receipt_date DATE NOT NULL,
  item_id TEXT NOT NULL,
  quantity_received REAL NOT NULL CHECK (quantity_received > 0)
);
CREATE INDEX idx_goods_receipts_po_line_id ON goods_receipts(po_line_id);

CREATE TABLE invoices (
  invoice_line_id TEXT PRIMARY KEY,
  invoice_id TEXT NOT NULL,
  vendor_invoice_reference TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  vendor_name_raw TEXT,
  po_id TEXT,
  po_line_id TEXT,
  invoice_date DATE NOT NULL,
  received_date DATE NOT NULL,
  item_id TEXT NOT NULL,
  invoice_quantity REAL NOT NULL CHECK (invoice_quantity > 0),
  unit_price REAL NOT NULL CHECK (unit_price >= 0),
  tax_rate REAL NOT NULL CHECK (tax_rate BETWEEN 0 AND 1),
  line_subtotal REAL NOT NULL,
  line_tax REAL NOT NULL,
  line_total REAL NOT NULL,
  currency TEXT NOT NULL,
  source_system TEXT NOT NULL,
  exception INTEGER NOT NULL CHECK (exception IN (0, 1)),
  exception_types TEXT,
  CHECK (line_total = ROUND(line_subtotal + line_tax, 2))
);
CREATE INDEX idx_invoices_invoice_id ON invoices(invoice_id);
CREATE INDEX idx_invoices_vendor_id ON invoices(vendor_id);

CREATE TABLE payments (
  payment_id TEXT PRIMARY KEY,
  invoice_id TEXT NOT NULL,
  payment_date DATE,
  payment_amount REAL,
  status TEXT NOT NULL CHECK (status IN ('Scheduled', 'Paid', 'Failed', 'Voided'))
);
CREATE INDEX idx_payments_invoice_id ON payments(invoice_id);

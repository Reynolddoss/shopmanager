/**
 * Shopkeeper notebook content — page-by-page guide for using Shop Manager.
 * Written for counter staff, not developers.
 */

export type ManualPage = {
  id: string;
  chapter: string;
  title: string;
  body: string[];
  fields?: { name: string; meaning: string }[];
  tip?: string;
};

export const MANUAL_PAGES: ManualPage[] = [
  {
    id: "cover",
    chapter: "Start",
    title: "Shop Manager notebook",
    body: [
      "This notebook explains how to run your shop day to day with this software.",
      "One install on this computer = one shop. Your data stays on this machine in a local database.",
      "Turn the pages with Next / Previous, or jump from the contents list on the left.",
      "If you are new: read Getting started, then Daily flow, then Inventory and Sales.",
    ],
    tip: "You do not need the internet for normal shop work. Backups are still important — see Settings.",
  },
  {
    id: "getting-started",
    chapter: "Start",
    title: "Getting started",
    body: [
      "First launch opens Sign in. If this computer has no shop yet, use Register a shop.",
      "Registration creates your shop name, owner login, and invoice prefix. After that, only Sign in is used.",
      "Keep the owner username and password safe. Multi-user cashier logins can be added later; for now one owner account is enough.",
      "After sign in you see the side menu: Dashboard, Inventory, Sales, and the rest.",
    ],
    fields: [
      { name: "Shop name", meaning: "Shown in the app header and on invoices." },
      { name: "Owner name / Username / Password", meaning: "Who signs in on this computer. Password needs at least 8 characters." },
      { name: "GSTIN / Phone / Address", meaning: "Optional shop identity for bills and settings." },
      { name: "Invoice prefix", meaning: "Letters used at the start of sale invoice numbers (e.g. SH)." },
    ],
    tip: "Already registered? You cannot register again on the same install — sign in instead.",
  },
  {
    id: "daily-flow",
    chapter: "Start",
    title: "Daily flow (recommended)",
    body: [
      "1. Sign in when you open the shop.",
      "2. Check Dashboard for today’s sales pulse and stock warnings.",
      "3. Add stock on a product’s Add stock tab (or post a Supplier bill if you have an invoice).",
      "4. Sell from Sales — search products, add lines, take payment or put on credit.",
      "5. Record customer/vendor Payments when money moves.",
      "6. Log Expenses (rent, power, tea) if you track them here.",
      "7. End of day: glance Analytics or Reports; optionally Backup now in Settings.",
    ],
    tip: "The top Smart Finder searches products by name, SKU, barcode, alias, and more — use it from any screen.",
  },
  {
    id: "dashboard",
    chapter: "Screens",
    title: "Dashboard",
    body: [
      "Home overview after login. Use it for a quick health check, not deep reports.",
      "Typical cards show sales activity, stock alerts, and shortcuts into busy areas.",
      "If something looks wrong after a restore, restart the app so totals refresh.",
    ],
  },
  {
    id: "inventory",
    chapter: "Screens",
    title: "Inventory list",
    body: [
      "Inventory is your product catalog plus live on-hand quantity.",
      "Filter or search to find an item. Click a row to open the product card.",
      "New product starts a short wizard (catalog only). Stock quantity is added afterward on Add stock.",
      "On-hand can be zero for a brand-new SKU until you receive the first lot.",
    ],
    fields: [
      { name: "Search / filters", meaning: "Narrow by text, category, brand, or stock status." },
      { name: "On hand", meaning: "Sum of remaining quantity across open batches (lots)." },
    ],
    tip: "Creating a product does not put stock on the shelf. Always Add stock (or a Supplier bill) next.",
  },
  {
    id: "new-product",
    chapter: "Screens",
    title: "New product wizard",
    body: [
      "Four steps: Identity → Classify → Details → Stock alerts.",
      "Hover the small i next to each field name for a short explanation.",
      "After Create product you land on Add stock so you can enter opening quantity.",
    ],
    fields: [
      { name: "Name", meaning: "What staff and customers recognise on screen and bills." },
      {
        name: "SKU",
        meaning: "Your unique shop code. Suggested from the name (Conduit Pipes → CP-00001). Must stay unique. Use Suggest to refresh.",
      },
      { name: "Barcode", meaning: "Optional scanner code from the manufacturer or your own labels." },
      { name: "Category / Brand / Unit", meaning: "Catalog placement. You can add a missing category, brand, or unit on the spot." },
      { name: "Specification tags", meaning: "Short chips like 25mm, PVC, Grey. Add with Enter; remove with ×." },
      { name: "HSN", meaning: "Optional GST classification code for invoices." },
      { name: "Search aliases", meaning: "Extra words so Finder matches shop slang (comma separated)." },
      { name: "Minimum stock / Reorder level", meaning: "Alert thresholds only — not the quantity you currently hold." },
    ],
  },
  {
    id: "product-detail",
    chapter: "Screens",
    title: "Product card & tabs",
    body: [
      "Each product has tabs: Overview, Stock, Vendors, Batches, Prices, Add stock.",
      "Overview shows identity, on-hand, and value.",
      "Batches lists every lot still holding quantity — old lots are never overwritten when new stock arrives.",
      "Stock lets you adjust quantity with a reason (opening stock, damage, count correction).",
      "Add stock is where you add a new lot with quantity and per-unit prices (no vendor payable).",
    ],
    tip: "Historical purchase costs stay on each batch. That is why selling and valuation stay accurate over time.",
  },
  {
    id: "receive-stock",
    chapter: "Screens",
    title: "Add stock (important)",
    body: [
      "Open the product → Add stock tab.",
      "Each time you add stock you create a new lot. Older lots are never overwritten — different vendor and different prices are normal.",
      "Enter how many units arrived and the prices for one unit on this lot — not the bill total.",
      "Example: Quantity 100, Purchase price 100 → ₹100 each → lot worth ₹10,000.",
      "Selling price, safe selling price, and MRP are also per unit for this lot.",
      "The last lot is shown only as a reference; you may copy its prices or enter new ones.",
      "Save as new lot — on-hand increases. FIFO still sells older lots first.",
    ],
    fields: [
      { name: "Vendor", meaning: "Optional supplier for this lot (can differ from the last lot)." },
      { name: "Quantity", meaning: "How many units in this lot." },
      { name: "Purchase price (per unit)", meaning: "Cost for one unit on this lot." },
      { name: "Selling price (per unit)", meaning: "Counter price for one unit from this lot." },
      { name: "Safe selling price", meaning: "Floor you try not to go below without care." },
    ],
    tip: "Have a supplier invoice to track what you owe? Use Supplier bills instead of Add stock.",
  },
  {
    id: "vendors",
    chapter: "Screens",
    title: "Vendors",
    body: [
      "Suppliers you buy from. Name is required; address and contacts are optional.",
      "Payable balance grows when you purchase on credit and falls when you pay the vendor.",
      "Keep phone, GSTIN, and address filled when you print or call often.",
    ],
    fields: [
      { name: "Supplier name", meaning: "Unique name for this vendor." },
      { name: "Contact / phones / email / address / GSTIN", meaning: "Optional master data for follow-up and paperwork." },
      { name: "Payable", meaning: "What you currently owe this vendor." },
    ],
  },
  {
    id: "customers",
    chapter: "Screens",
    title: "Customers",
    body: [
      "Save each buyer with a name, mobile number, and type (Electrician, General, Contractor, …).",
      "Mobile is the practical identifier — use it on the bill screen to link purchases to the same person.",
      "Linked customers unlock credit balances, frequent-buyer analytics, and (later) loyalty points.",
      "Use Payments to record money received against a customer.",
    ],
    fields: [
      { name: "Name", meaning: "Shown on invoices and in analytics." },
      { name: "Mobile", meaning: "Main way to find returning customers at the counter." },
      { name: "Type", meaning: "Electrician / General / Contractor / etc. for reporting." },
      { name: "Address / notes", meaning: "Optional site or reminder details." },
      { name: "Balance", meaning: "Outstanding receivable for that customer." },
      { name: "Loyalty points", meaning: "Stored for a future rewards programme; not awarded yet." },
    ],
  },
  {
    id: "purchases",
    chapter: "Screens",
    title: "Supplier bills",
    body: [
      "Post a vendor invoice: pick supplier, add products with qty/cost/selling prices, optional amount paid now.",
      "This creates stock lots and increases what you owe the vendor (unless fully paid).",
      "Use History → Purchases to browse these bills later.",
    ],
    tip: "Opening stock or cash top-up with no invoice? Use product → Add stock instead.",
  },
  {
    id: "sales",
    chapter: "Screens",
    title: "Sales (billing)",
    body: [
      "Build a bill: choose customer (or walk-in flow as designed), search products, set qty and unit price.",
      "Stock is taken from oldest lots first (FIFO) so older purchase costs leave first.",
      "Amount paid vs total decides cash/partial/credit behaviour with the customer ledger.",
      "Print or view invoice after a successful sale when the invoice action is shown.",
    ],
    fields: [
      { name: "Customer", meaning: "Who is billed; needed for credit tracking." },
      { name: "Line quantity / unit price", meaning: "Per-unit selling price × quantity for that line." },
      { name: "Amount paid / payment method", meaning: "What was collected now; remainder may stay receivable." },
    ],
    tip: "If stock is insufficient, the sale is blocked until you receive more or reduce quantity.",
  },
  {
    id: "history",
    chapter: "Screens",
    title: "History",
    body: [
      "Browse past sale bills and purchase documents by date range or search.",
      "Open a bill to see line items, payment (cash change / UPI ref), and print the invoice again.",
    ],
    fields: [
      { name: "Sale bills", meaning: "Customer invoices posted from Bill / Sales." },
      { name: "Purchases", meaning: "Supplier bills from the Supplier bills screen." },
    ],
  },
  {
    id: "payments",
    chapter: "Screens",
    title: "Payments",
    body: [
      "Record money in or out against a customer or vendor without creating a new sale/purchase.",
      "Use after a credit sale when the customer returns to pay, or when you clear a vendor payable.",
      "Always pick the correct party type and id/name so the ledger stays clean.",
    ],
    fields: [
      { name: "Party type", meaning: "Customer or Vendor." },
      { name: "Amount / method", meaning: "How much moved and how (cash, UPI, etc.)." },
    ],
  },
  {
    id: "expenses",
    chapter: "Screens",
    title: "Expenses",
    body: [
      "Shop running costs that are not stock purchases — rent, electricity, transport, miscellaneous.",
      "Pick a category, amount, and optional notes. These feed expense totals in Analytics.",
    ],
  },
  {
    id: "analytics-reports",
    chapter: "Screens",
    title: "Analytics & Reports",
    body: [
      "Analytics: filter by dates, category, brand; review sales, expenses, discounts, outstanding.",
      "Export CSV when you need a spreadsheet. Print when you need a paper copy.",
      "Reports: printable summaries for the counter or accountant.",
      "Use these for weekly review; use Dashboard for morning glance.",
    ],
  },
  {
    id: "settings",
    chapter: "Screens",
    title: "Settings, theme & backup",
    body: [
      "Appearance: Midnight (default dark), Slate, or Paper (light). Preview applies immediately; Save settings to keep it.",
      "Shop identity: name, GSTIN, phone, address, invoice prefix — edit anytime.",
      "Backup now creates a validated snapshot. Restore asks for confirm and keeps a safety copy first.",
      "Scheduled backup can run while the app is open if you enable it.",
    ],
    fields: [
      { name: "Theme", meaning: "Screen colours for this shop install." },
      { name: "Backup / Restore", meaning: "Protect against disk failure or mistakes. Restore replaces the live shop file." },
    ],
    tip: "After a restore, restart if numbers look stale. Never store the only backup on the same failing drive.",
  },
  {
    id: "finder",
    chapter: "Tools",
    title: "Smart Finder",
    body: [
      "The search box in the top bar finds products without opening Inventory first.",
      "Try partial names, SKU, barcode, aliases, brand, or category words.",
      "Click a result to jump to that product.",
    ],
  },
  {
    id: "pricing-rules",
    chapter: "Tools",
    title: "Pricing rules of thumb",
    body: [
      "Purchase price, MRP, selling price, and safe price on Add stock / Supplier bills are always per unit.",
      "Lot total ≈ quantity × effective unit cost (after supplier discount).",
      "Safe selling price is your warning floor; enforce-or-warn behaviour follows shop settings.",
      "Changing price on a new batch does not rewrite old batches — history stays intact.",
    ],
  },
  {
    id: "troubleshoot",
    chapter: "Help",
    title: "If something goes wrong",
    body: [
      "API offline in the footer: start the local Django server (or packaged backend) and refresh.",
      "Cannot register: this install already has a shop — sign in.",
      "Cannot sell: check on-hand on the product; receive stock first.",
      "Duplicate SKU error: change SKU or press Suggest for a free serial.",
      "Wrong theme: Settings → Appearance → save.",
      "Lost data fear: create a Backup now before risky restores or PC moves.",
    ],
    tip: "Sign out is in the footer. Closing the window without backup is fine for a short break; still keep regular backups.",
  },
];

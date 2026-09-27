/**
 * Shared app navigation: grouped sidebar + home launch tiles.
 * Icons are inline SVGs so we do not add an icon package.
 */

export type NavIconId =
  | "home"
  | "bill"
  | "history"
  | "inventory"
  | "catalog"
  | "analytics"
  | "customers"
  | "vendors"
  | "purchases"
  | "payments"
  | "expenses"
  | "reports"
  | "manual"
  | "settings";

export type NavItem = {
  to: string;
  label: string;
  icon: NavIconId;
  /** Short blurb on the home grid. */
  blurb?: string;
  /** Show as a large tile on the home screen. */
  home?: boolean;
};

export type NavGroup = {
  id: string;
  label: string;
  items: NavItem[];
};

export const NAV_GROUPS: NavGroup[] = [
  {
    id: "home",
    label: "Home",
    items: [{ to: "/", label: "Home", icon: "home", blurb: "Shortcuts and today’s summary", home: true }],
  },
  {
    id: "counter",
    label: "Counter",
    items: [
      { to: "/sales", label: "Bill", icon: "bill", blurb: "Counter sale and invoice", home: true },
      { to: "/history", label: "History", icon: "history", blurb: "Browse past bills and purchases", home: true },
      { to: "/payments", label: "Payments", icon: "payments", blurb: "Receive or pay against ledgers", home: true },
    ],
  },
  {
    id: "stock",
    label: "Stock",
    items: [
      { to: "/inventory", label: "Inventory", icon: "inventory", blurb: "Products, lots, receive stock", home: true },
      {
        to: "/catalog",
        label: "Catalog",
        icon: "catalog",
        blurb: "Brands, categories, units, tags",
        home: true,
      },
      { to: "/purchases", label: "Supplier bills", icon: "purchases", blurb: "Vendor invoice + stock + payables", home: true },
      { to: "/vendors", label: "Vendors", icon: "vendors", blurb: "Supplier directory", home: true },
    ],
  },
  {
    id: "people",
    label: "People",
    items: [
      { to: "/customers", label: "Customers", icon: "customers", blurb: "Buyers, mobile, type", home: true },
    ],
  },
  {
    id: "money",
    label: "Money",
    items: [
      { to: "/expenses", label: "Expenses", icon: "expenses", blurb: "Shop running costs", home: true },
    ],
  },
  {
    id: "insights",
    label: "Insights",
    items: [
      { to: "/analytics", label: "Analytics", icon: "analytics", blurb: "Sales, profit, frequent buyers", home: true },
      { to: "/reports", label: "Reports", icon: "reports", blurb: "Printed / export reports", home: true },
    ],
  },
  {
    id: "system",
    label: "System",
    items: [
      { to: "/manual", label: "Manual", icon: "manual", blurb: "How to use the shop app", home: true },
      { to: "/settings", label: "Settings", icon: "settings", blurb: "Shop profile and theme", home: true },
    ],
  },
];

/** Flat list used by the home icon grid (excludes the Home tile itself). */
export const HOME_TILES: NavItem[] = NAV_GROUPS.flatMap((group) => group.items).filter(
  (item) => item.home && item.to !== "/",
);

const strokeProps = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

/** Small SVG glyphs for sidebar and home tiles. */
export const NavIcon = ({ id, className = "h-5 w-5" }: { id: NavIconId; className?: string }) => {
  const common = { className, viewBox: "0 0 24 24", "aria-hidden": true as const };
  switch (id) {
    case "home":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5z" />
        </svg>
      );
    case "bill":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M7 4h10v16l-2-1.2L13 20l-2-1.2L9 20l-2-1.2V4z" />
          <path {...strokeProps} d="M9 8h6M9 12h6M9 16h3" />
        </svg>
      );
    case "history":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M4 12a8 8 0 1 0 2.3-5.6" />
          <path {...strokeProps} d="M4 5v4h4" />
          <path {...strokeProps} d="M12 8v5l3 2" />
        </svg>
      );
    case "inventory":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M4 8h16v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V8z" />
          <path {...strokeProps} d="M8 8V6a4 4 0 0 1 8 0v2" />
        </svg>
      );
    case "catalog":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M5 5h14v14H5z" />
          <path {...strokeProps} d="M9 5v14M5 10h14M5 15h14" />
        </svg>
      );
    case "analytics":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M4 19h16" />
          <path {...strokeProps} d="M7 16V10M12 16V7M17 16v-5" />
        </svg>
      );
    case "customers":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M16 19v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1" />
          <circle {...strokeProps} cx="9.5" cy="8" r="3" />
          <path {...strokeProps} d="M19 19v-1a3.5 3.5 0 0 0-2.5-3.35M16.5 5.1a3 3 0 0 1 0 5.8" />
        </svg>
      );
    case "vendors":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M3 10h18l-1.5 9H4.5L3 10z" />
          <path {...strokeProps} d="M5 10 7 4h10l2 6" />
        </svg>
      );
    case "purchases":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M4 7h16v12H4z" />
          <path {...strokeProps} d="M8 7V5a4 4 0 0 1 8 0v2" />
          <path {...strokeProps} d="M9 13h6" />
        </svg>
      );
    case "payments":
      return (
        <svg {...common}>
          <rect {...strokeProps} x="3" y="6" width="18" height="12" rx="2" />
          <path {...strokeProps} d="M3 10h18" />
          <path {...strokeProps} d="M7 15h3" />
        </svg>
      );
    case "expenses":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M12 3v18" />
          <path {...strokeProps} d="M8 7h5.5a2.5 2.5 0 0 1 0 5H9a2.5 2.5 0 0 0 0 5H16" />
        </svg>
      );
    case "reports":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M7 3h7l5 5v13H7z" />
          <path {...strokeProps} d="M14 3v5h5M10 13h6M10 17h4" />
        </svg>
      );
    case "manual":
      return (
        <svg {...common}>
          <path {...strokeProps} d="M5 4h6a3 3 0 0 1 3 3v13a2.5 2.5 0 0 0-2.5-2.5H5z" />
          <path {...strokeProps} d="M19 4h-6a3 3 0 0 0-3 3v13a2.5 2.5 0 0 1 2.5-2.5H19z" />
        </svg>
      );
    case "settings":
      return (
        <svg {...common}>
          <circle {...strokeProps} cx="12" cy="12" r="3" />
          <path
            {...strokeProps}
            d="M12 3.5v2.2M12 18.3v2.2M4.9 7.1l1.6 1.6M17.5 15.3l1.6 1.6M3.5 12h2.2M18.3 12h2.2M4.9 16.9l1.6-1.6M17.5 8.7l1.6-1.6"
          />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle {...strokeProps} cx="12" cy="12" r="8" />
        </svg>
      );
  }
};

export type AuthShop = {
  name: string;
  gstin: string;
  phone: string;
  ui_theme?: string;
};

export type AuthUser = {
  id: number;
  username: string;
  full_name: string;
  is_owner: boolean;
};

export type AuthStatusResponse = {
  registered: boolean;
  authenticated: boolean;
  shop: AuthShop | null;
  user: AuthUser | null;
};

export type RegisterPayload = {
  shop_name: string;
  owner_name: string;
  username: string;
  password: string;
  confirm_password: string;
  phone?: string;
  address?: string;
  gstin?: string;
  invoice_prefix?: string;
  email?: string;
};

export type LoginPayload = {
  username: string;
  password: string;
};

export type HealthResponse = {
  status: string;
  database: string;
  integrity_check: string;
  journal_mode: string;
  recovery_message?: string;
};

export type VersionResponse = {
  name: string;
  version: string;
  api: string;
};

export type ApiError = {
  error: {
    code: string;
    message: string;
    details: unknown;
  };
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type FinderRow = {
  id: number;
  name: string;
  sku: string;
  barcode: string;
  specification: string;
  brand_name: string;
  category_name: string;
  current_stock: string;
  stock_status: string;
  active_batch_id: number | null;
  active_cost: string | null;
  active_selling_price: string | null;
  active_safe_selling_price: string | null;
  active_max_discount: string | null;
  active_mrp: string | null;
  next_lot_code: string | null;
  latest_batch_id: number | null;
  latest_selling_price: string | null;
  latest_cost: string | null;
  latest_mrp: string | null;
  latest_lot_code: string | null;
  image_url?: string | null;
  preferred_vendor: string | null;
  last_purchase_price: string | null;
  lowest_historical_purchase_price: string | null;
};

export type NamedRef = { id: number; name: string; is_active: boolean };

export type ProductRecord = {
  id: number;
  name: string;
  sku: string;
  barcode: string;
  category: number;
  brand: number | null;
  unit: number;
  specification: string;
  hsn_code: string;
  gst_rate: string;
  mrp: string;
  default_selling_price: string;
  default_safe_selling_price: string;
  default_maximum_discount_percent: string;
  is_active: boolean;
  storage_location: string;
  min_stock_quantity: string;
  max_stock_quantity: string;
  reorder_level: string;
  image_url?: string | null;
  aliases: { id: number; term: string }[];
};

export type ProductCard = {
  product: ProductRecord;
  stock: {
    on_hand: string;
    status: string;
    min_stock_quantity: string;
    max_stock_quantity: string;
    reorder_level: string;
    valuation_method: string;
    on_hand_value: string;
  };
  pricing: {
    lot_code?: string;
    mrp: string;
    selling_price: string;
    safe_selling_price: string;
    maximum_discount_percent: string;
    current_cost: string;
    gross_margin: string;
    margin_percent: string;
    price_after_max_discount: string;
    below_safe_if_max_discount: boolean;
  } | null;
  pricing_latest?: {
    lot_code?: string;
    mrp: string;
    selling_price: string;
    safe_selling_price: string;
    maximum_discount_percent: string;
    current_cost: string;
  } | null;
  vendors: {
    id: number;
    vendor: number;
    vendor_name: string;
    last_purchase_price: string | null;
    lowest_historical_purchase_price: string | null;
    last_purchase_date: string | null;
    is_preferred: boolean;
  }[];
  batches: {
    id: number;
    lot_code: string;
    vendor_name: string;
    purchase_date: string | null;
    purchase_cost: string;
    selling_price: string;
    safe_selling_price: string;
    maximum_discount_percent: string;
    remaining_quantity: string;
    original_quantity: string;
  }[];
};

export type PreviousBatchPayload = {
  detected: boolean;
  previous: {
    id: number;
    lot_code: string;
    vendor_name: string;
    purchase_date: string | null;
    purchase_cost: string;
    selling_price: string;
    safe_selling_price: string;
    maximum_discount_percent: string;
    remaining_quantity: string;
  } | null;
  new_cost?: string;
  cost_difference?: string;
  cost_percent_change?: string;
};

/**
 * Typed HTTP client for /api/v1/. Pricing and stock math stay on the server.
 */
export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = "/api/v1") {
    this.baseUrl = baseUrl;
  }

  request = async <T>(path: string, init?: RequestInit): Promise<T> => {
    const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
    const headers = new Headers(init?.headers ?? undefined);
    // Browser must set multipart boundary itself — never force JSON on FormData.
    if (isFormData) {
      headers.delete("Content-Type");
    } else if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const response = await fetch(`${this.baseUrl}${path}`, {
      credentials: "include",
      ...init,
      headers,
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as ApiError | null;
      throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  };

  get = async <T>(path: string): Promise<T> => this.request<T>(path);

  post = async <T>(path: string, body: unknown): Promise<T> =>
    this.request<T>(path, { method: "POST", body: JSON.stringify(body) });

  patch = async <T>(path: string, body: unknown): Promise<T> =>
    this.request<T>(path, { method: "PATCH", body: JSON.stringify(body) });

  /** Upload or replace a product catalog photo (multipart). */
  uploadProductImage = async <T = ProductRecord>(productId: number, file: File): Promise<T> => {
    const body = new FormData();
    body.append("image", file);
    return this.request<T>(`/products/${productId}/image/`, { method: "POST", body });
  };

  /** Remove the catalog photo from a product. */
  clearProductImage = async <T = ProductRecord>(productId: number): Promise<T> =>
    this.request<T>(`/products/${productId}/image/`, { method: "DELETE" });

  getAuthStatus = async (): Promise<AuthStatusResponse> => this.get<AuthStatusResponse>("/auth/status/");

  registerShop = async (payload: RegisterPayload): Promise<AuthStatusResponse> =>
    this.post<AuthStatusResponse>("/auth/register/", payload);

  login = async (payload: LoginPayload): Promise<AuthStatusResponse> =>
    this.post<AuthStatusResponse>("/auth/login/", payload);

  logout = async (): Promise<{ authenticated: boolean }> =>
    this.post<{ authenticated: boolean }>("/auth/logout/", {});
}

export const apiClient = new ApiClient();


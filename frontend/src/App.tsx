import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthProvider.tsx";
import { AppShell } from "./layouts/AppShell.tsx";
import { AnalyticsPage } from "./pages/AnalyticsPage.tsx";
import { CatalogPage } from "./pages/CatalogPage.tsx";
import { DashboardPage } from "./pages/DashboardPage.tsx";
import { ExpensesPage } from "./pages/ExpensesPage.tsx";
import { HistoryPage } from "./pages/HistoryPage.tsx";
import { InventoryPage } from "./pages/InventoryPage.tsx";
import { LoginPage } from "./pages/LoginPage.tsx";
import { CustomersPage, VendorsPage } from "./pages/PartiesPages.tsx";
import { PaymentsPage } from "./pages/PaymentsPage.tsx";
import { ProductCreatePage } from "./pages/ProductCreatePage.tsx";
import { ProductDetailPage } from "./pages/ProductDetailPage.tsx";
import { PurchasesPage } from "./pages/PurchasesPage.tsx";
import { RegisterPage } from "./pages/RegisterPage.tsx";
import { ReportsPage } from "./pages/ReportsPage.tsx";
import { SalesPage } from "./pages/SalesPage.tsx";
import { ManualPageView } from "./pages/ManualPage.tsx";
import { SettingsPage } from "./pages/SettingsPage.tsx";

const AuthGate = () => {
  const { phase, guestView, error } = useAuth();

  if (phase === "loading") {
    return (
      <div className="flex min-h-full items-center justify-center bg-[var(--paper)] p-8 font-sans text-sm text-[var(--muted)]">
        {error || "Connecting to local API…"}
      </div>
    );
  }

  if (phase === "guest") {
    return guestView === "register" ? <RegisterPage /> : <LoginPage />;
  }

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/inventory/new" element={<ProductCreatePage />} />
        <Route path="/inventory/:productId" element={<ProductDetailPage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/vendors" element={<VendorsPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/purchases" element={<PurchasesPage />} />
        <Route path="/sales" element={<SalesPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/payments" element={<PaymentsPage />} />
        <Route path="/expenses" element={<ExpensesPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/manual" element={<ManualPageView />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
};

export const App = () => (
  <Routes>
    <Route path="*" element={<AuthGate />} />
  </Routes>
);

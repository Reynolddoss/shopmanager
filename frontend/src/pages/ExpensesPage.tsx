import { useEffect, useState } from "react";
import { apiClient, type Paginated } from "../services/api.ts";
import { formatMoney, sanitizeDecimalInput } from "../utils/money.ts";

type Category = { id: number; name: string };
type ExpenseRow = { id: number; category: number; category_name: string; expense_date: string; amount: string; notes: string };

export const ExpensesPage = () => {
  const [categories, setCategories] = useState<Category[]>([]);
  const [rows, setRows] = useState<ExpenseRow[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const today = new Date().toISOString().slice(0, 10);

  const reload = () => {
    void apiClient.get<Paginated<ExpenseRow>>("/expenses/").then((page) => setRows(page.results));
  };

  useEffect(() => {
    void apiClient.get<Paginated<Category>>("/expense-categories/").then((page) => setCategories(page.results));
    reload();
  }, []);

  return (
    <section>
      <h2 className="text-3xl">Expenses</h2>
      <p className="mt-2 font-sans text-sm text-[var(--muted)]">Operating costs only. Stock purchases stay on the Purchases page.</p>
      <form
        className="mt-6 grid max-w-xl gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void apiClient
            .post("/expenses/", { category: Number(categoryId), expense_date: today, amount, notes })
            .then(() => {
              setAmount("");
              setNotes("");
              reload();
            });
        }}
      >
        <select className="h-10 rounded-md border px-3 font-sans text-sm" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          <option value="">Category</option>
          {categories.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <input
          className="h-10 rounded-md border px-3 font-sans text-sm"
          value={amount}
          onChange={(e) => setAmount(sanitizeDecimalInput(e.target.value, 2))}
          placeholder="Amount"
        />
        <input className="h-10 rounded-md border px-3 font-sans text-sm" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes" />
        <button className="rounded-md bg-[var(--accent)] px-3 py-2 font-sans text-sm text-white" type="submit">
          Save expense
        </button>
      </form>
      <ul className="mt-6 font-sans text-sm">
        {rows.map((row) => (
          <li key={row.id}>
            {row.expense_date} · {row.category_name} · ₹{formatMoney(row.amount)}
          </li>
        ))}
      </ul>
    </section>
  );
};

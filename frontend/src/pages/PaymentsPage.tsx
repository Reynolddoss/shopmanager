import { useState } from "react";
import { apiClient } from "../services/api.ts";
import { sanitizeDecimalInput } from "../utils/money.ts";

export const PaymentsPage = () => {
  const [partyType, setPartyType] = useState("CUSTOMER");
  const [partyId, setPartyId] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("CASH");
  const [message, setMessage] = useState("");
  return (
    <section>
      <h2 className="text-3xl">Payments</h2>
      <form
        className="mt-6 grid max-w-md gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void apiClient
            .post("/payments/", { party_type: partyType, party_id: Number(partyId), amount, method })
            .then(() => setMessage("Payment posted to ledger."))
            .catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Failed"));
        }}
      >
        <select className="h-10 rounded-md border px-3 font-sans text-sm" value={partyType} onChange={(e) => setPartyType(e.target.value)}>
          <option>CUSTOMER</option>
          <option>VENDOR</option>
        </select>
        <input className="h-10 rounded-md border px-3 font-sans text-sm" value={partyId} onChange={(e) => setPartyId(e.target.value)} placeholder="Party id" />
        <input
          className="h-10 rounded-md border px-3 font-sans text-sm"
          value={amount}
          onChange={(e) => setAmount(sanitizeDecimalInput(e.target.value, 2))}
          placeholder="Amount"
        />
        <select className="h-10 rounded-md border px-3 font-sans text-sm" value={method} onChange={(e) => setMethod(e.target.value)}>
          {["CASH", "UPI", "CARD", "BANK"].map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
        <button className="rounded-md bg-[var(--accent)] px-3 py-2 font-sans text-sm text-white" type="submit">
          Record payment
        </button>
      </form>
      {message ? <p className="mt-3 font-sans text-sm">{message}</p> : null}
    </section>
  );
};

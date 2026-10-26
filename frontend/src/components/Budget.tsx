import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { Budget } from "../api/types";
import { inr } from "../lib/format";
import { EstimatedLabel } from "./ui";

const LINES: { key: keyof Budget; label: string; colour: string }[] = [
  { key: "outbound", label: "Travel there", colour: "#0b5e58" },
  { key: "return", label: "Travel back", colour: "#3aa79b" },
  { key: "stay", label: "Stay", colour: "#9a4a07" },
  { key: "food", label: "Food", colour: "#d9a441" },
  { key: "entry_fees", label: "Entry fees", colour: "#5b6676" },
  { key: "local_travel", label: "Local travel", colour: "#a6b0bd" },
];

export function BudgetDonut({ budget }: { budget: Budget }) {
  const data = LINES.map((l) => ({ name: l.label, value: budget[l.key] as number, colour: l.colour })).filter((d) => d.value > 0);
  return (
    <figure data-estimate aria-label={`Budget chart: estimated total ${inr(budget.total)}`} className="flex flex-col items-center print:hidden">
      <div className="h-56 w-full max-w-xs" aria-hidden>
        <ResponsiveContainer>
          <PieChart accessibilityLayer={false}>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="85%" isAnimationActive={false} rootTabIndex={-1}>
              {data.map((d) => <Cell key={d.name} fill={d.colour} />)}
            </Pie>
            <Tooltip formatter={(v: number) => inr(v)} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="text-center text-sm text-ink-700">Estimated total <strong>{inr(budget.total)}</strong></figcaption>
    </figure>
  );
}

export function BudgetTable({ budget }: { budget: Budget }) {
  return (
    <table data-estimate className="w-full text-sm">
      <caption className="mb-2 text-left"><EstimatedLabel /></caption>
      <tbody>
        {LINES.map((l) => (
          <tr key={l.key} className="border-b border-sand-200">
            <th scope="row" className="py-1 text-left font-normal">
              <span aria-hidden className="mr-2 inline-block h-2.5 w-2.5 rounded-sm" style={{ background: l.colour }} />{l.label}
            </th>
            <td className="py-1 text-right num">{inr(budget[l.key] as number)}</td>
          </tr>
        ))}
        <tr className="border-b border-sand-300 font-semibold">
          <th scope="row" className="py-1 text-left">Plan total (estimated)</th>
          <td className="py-1 text-right num">{inr(budget.total)}</td>
        </tr>
        <tr className="border-b border-sand-200">
          <th scope="row" className="py-1 text-left font-normal">Contingency (10%, kept aside)</th>
          <td className="py-1 text-right num">{inr(budget.contingency)}</td>
        </tr>
        <tr className="text-ink-700">
          <th scope="row" className="py-1 text-left font-normal">Unused within the plannable budget</th>
          <td className="py-1 text-right num">{inr(budget.usable_budget - budget.total)}</td>
        </tr>
        <tr className="font-semibold">
          <th scope="row" className="py-1 text-left">Your budget</th>
          <td className="py-1 text-right num">{inr(budget.budget_total)}</td>
        </tr>
      </tbody>
    </table>
  );
}

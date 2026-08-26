import type { Finding } from "../types";
import { severityTone } from "../lib/format";

export function FindingRow({ finding }: { finding: Finding }) {
  return (
    <li className="flex gap-2.5 border-t border-line py-2 first:border-t-0">
      <span
        className="mt-[7px] size-1.5 shrink-0 rounded-full"
        style={{ background: `var(--color-${severityTone(finding.severity)})` }}
        aria-hidden
      />
      <div className="min-w-0">
        <p className="text-[13px] font-medium leading-snug">{finding.title}</p>
        <p className="mt-0.5 text-[12px] leading-snug text-muted">{finding.detail}</p>
      </div>
    </li>
  );
}

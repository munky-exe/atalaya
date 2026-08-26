import { useState } from "react";
import type { Domain } from "../types";
import { relativeTime } from "../lib/format";
import { GradeMark } from "./GradeMark";
import { LifetimeBar } from "./LifetimeBar";
import { FindingRow } from "./FindingRow";

interface Props {
  domain: Domain;
  onRecheck: (id: number) => Promise<void>;
  onRemove: (id: number) => Promise<void>;
}

export function DomainCard({ domain, onRecheck, onRemove }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const check = domain.latest;

  async function recheck() {
    setBusy(true);
    try {
      await onRecheck(domain.id);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="rounded-lg border border-line bg-surface p-4 transition-colors hover:border-line-bright">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate font-mono text-[13.5px] font-medium">{domain.hostname}</h2>
          {domain.label && (
            <p className="mt-0.5 truncate text-[11.5px] text-faint">{domain.label}</p>
          )}
        </div>
        {check && <GradeMark grade={check.grade} score={check.score} />}
      </header>

      <div className="mt-4">
        <LifetimeBar check={check} />
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3 font-mono text-[11px]">
        <Stat label="Protocolo" value={check?.protocol ?? "—"} />
        <Stat label="Cifrado" value={check?.cipher_bits ? `${check.cipher_bits} bits` : "—"} />
        <Stat
          label="Handshake"
          value={check?.handshake_ms != null ? `${check.handshake_ms} ms` : "—"}
        />
      </dl>

      {check && check.findings.length > 0 && (
        <ul className="mt-4">
          {check.findings.slice(0, open ? undefined : 2).map((finding) => (
            <FindingRow key={finding.code} finding={finding} />
          ))}
        </ul>
      )}

      {open && check && (
        <dl className="mt-4 space-y-2 border-t border-line pt-3 font-mono text-[11px]">
          <Row label="Emisor" value={check.issuer} />
          <Row label="Sujeto" value={check.subject} />
          <Row label="IP" value={check.resolved_ip} />
          <Row label="Suite" value={check.cipher} />
        </dl>
      )}

      <footer className="mt-4 flex items-center justify-between border-t border-line pt-3">
        <span className="font-mono text-[10.5px] text-faint">
          {check ? relativeTime(check.observed_at) : "sin revisar"}
        </span>
        <div className="flex items-center gap-1">
          <Action onClick={() => setOpen((v) => !v)}>{open ? "Menos" : "Detalle"}</Action>
          <Action onClick={recheck} disabled={busy}>
            {busy ? "..." : "Revisar"}
          </Action>
          <Action onClick={() => onRemove(domain.id)} tone="fail">
            Quitar
          </Action>
        </div>
      </footer>
    </article>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wider text-faint">{label}</dt>
      <dd className="tnum mt-0.5 truncate">{value}</dd>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex gap-3">
      <dt className="w-16 shrink-0 text-faint">{label}</dt>
      <dd className="min-w-0 break-all text-muted">{value ?? "—"}</dd>
    </div>
  );
}

function Action({
  children,
  onClick,
  disabled,
  tone,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  tone?: "fail";
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="rounded px-2 py-1 text-[11.5px] text-muted transition-colors
                 hover:bg-raised hover:text-text disabled:opacity-40"
      style={tone === "fail" ? { color: "var(--color-fail)" } : undefined}
    >
      {children}
    </button>
  );
}
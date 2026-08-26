import { LifetimeBar } from "./components/LifetimeBar";
import type { Check } from "./types";

const dia = 86_400_000;

function fake(beforeDays: number, afterDays: number): Check {
  return {
    id: 1,
    observed_at: new Date().toISOString(),
    score: 100,
    grade: "A",
    reachable: true,
    resolved_ip: null,
    handshake_ms: null,
    protocol: "TLSv1.3",
    cipher: null,
    cipher_bits: 256,
    issuer: null,
    subject: null,
    not_before: new Date(Date.now() - beforeDays * dia).toISOString(),
    not_after: new Date(Date.now() + afterDays * dia).toISOString(),
    findings: [],
    legacy_accepted: [],
    legacy_untestable: [],
    error: null,
  };
}

const casos: [string, Check][] = [
  ["Recién renovado, 90 días", fake(2, 88)],
  ["A la mitad", fake(45, 45)],
  ["38 sobre 89 — rutina", fake(51, 38)],
  ["38 sobre 730 — urgencia", fake(692, 38)],
  ["Vence en 5 días", fake(85, 5)],
  ["Vencido hace 3", fake(93, -3)],
];

export default function App() {
  return (
    <div className="min-h-screen p-10">
      <h1 className="text-2xl font-bold tracking-tight">Barra de vida</h1>
      <p className="mt-2 max-w-md text-[13px] text-muted">
        Compara los casos tres y cuatro: mismos días restantes, urgencia
        distinta. Eso es lo que un número solo no puede decir.
      </p>

      <div className="mt-8 grid max-w-3xl gap-5 sm:grid-cols-2">
        {casos.map(([titulo, check]) => (
          <div key={titulo} className="rounded-lg border border-line bg-surface p-4">
            <p className="mb-3 font-mono text-[11px] text-muted">{titulo}</p>
            <LifetimeBar check={check} />
          </div>
        ))}
      </div>
    </div>
  );
}

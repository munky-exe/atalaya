import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "./lib/api";
import type { Domain } from "./types";
import { AddDomain } from "./components/AddDomain";
import { DomainCard } from "./components/DomainCard";

export default function App() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setDomains(await api.listDomains());
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Cada accion actualiza el estado local con lo que devolvio la API, en
  // lugar de recargar la lista completa. Menos peticiones y sin parpadeo.
  const addDomain = async (hostname: string) => {
    const created = await api.addDomain(hostname);
    setDomains((current) => [...current, created].sort(byHostname));
  };

  const recheck = async (id: number) => {
    const check = await api.checkNow(id);
    setDomains((current) => current.map((d) => (d.id === id ? { ...d, latest: check } : d)));
  };

  const remove = async (id: number) => {
    await api.remove(id);
    setDomains((current) => current.filter((d) => d.id !== id));
  };

  const summary = useMemo(() => {
    const checked = domains.filter((d) => d.latest);
    const failing = checked.filter((d) => ["D", "E", "F"].includes(d.latest!.grade)).length;
    const expiring = checked.filter((d) => {
      const notAfter = d.latest!.not_after;
      if (!notAfter) return false;
      const days = (new Date(notAfter).getTime() - Date.now()) / 86400000;
      return days >= 0 && days < 30;
    }).length;
    return { total: domains.length, failing, expiring };
  }, [domains]);

  return (
    <div className="min-h-screen">
      <header className="horizon relative border-b border-line">
        <div className="mx-auto max-w-6xl px-5 pb-8 pt-12">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-faint">
            Postura TLS
          </p>
          <h1 className="mt-2 text-[38px] font-bold leading-none tracking-tight">Atalaya</h1>
          <p className="mt-3 max-w-lg text-[14px] leading-relaxed text-muted">
            Vigila el certificado y la configuracion de transporte de tus dominios.
            Sabe cuanto les queda de vida, no solo si responden.
          </p>

          <div className="mt-7 flex flex-wrap items-end justify-between gap-5">
            <AddDomain onAdd={addDomain} disabled={loading} />
            <dl className="flex gap-6 font-mono text-[11px]">
              <Metric label="Vigilados" value={summary.total} />
              <Metric label="Por vencer" value={summary.expiring} tone="warm" />
              <Metric label="Reprobados" value={summary.failing} tone="fail" />
            </dl>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">
        {error && (
          <p
            className="rounded-md border border-line bg-surface p-4 text-[13px]"
            style={{ color: "var(--color-fail)" }}
            role="alert"
          >
            {error}
          </p>
        )}

        {loading && !error && <p className="text-[13px] text-faint">Cargando...</p>}

        {!loading && !error && domains.length === 0 && (
          <div className="rounded-lg border border-dashed border-line p-10 text-center">
            <p className="text-[14px] text-muted">Aun no vigilas ningun dominio.</p>
            <p className="mt-1 text-[13px] text-faint">
              Escribe uno arriba y lo reviso de inmediato.
            </p>
          </div>
        )}

        <div className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {domains.map((domain) => (
            <DomainCard
              key={domain.id}
              domain={domain}
              onRecheck={recheck}
              onRemove={remove}
            />
          ))}
        </div>
      </main>

      <footer className="mx-auto max-w-6xl px-5 pb-10">
        <p className="border-t border-line pt-5 font-mono text-[11px] text-faint">
          Los chequeos son pasivos: un handshake TLS por dominio, nada intrusivo.
        </p>
      </footer>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wider text-faint">{label}</dt>
      <dd
        className="tnum mt-1 text-[20px] font-bold leading-none"
        style={tone && value > 0 ? { color: `var(--color-${tone})` } : undefined}
      >
        {value}
      </dd>
    </div>
  );
}

function byHostname(a: Domain, b: Domain) {
  return a.hostname.localeCompare(b.hostname);
}

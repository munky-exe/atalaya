import type { Check } from "../types";
import { daysRemaining, formatDate, lifetimeProgress } from "../lib/format";

/**
 * La barra de vida del certificado.
 *
 * Toda otra herramienta imprime "vence en 38 días" y te deja adivinar si eso
 * es temprano o tarde. Esta dibuja la ventana completa de vigencia con un
 * marcador para hoy, así la proporción de vida restante se ve de un vistazo:
 * 38 días sobre un certificado de 89 se lee muy distinto que sobre uno de dos
 * años.
 */
export function LifetimeBar({ check }: { check: Check | null }) {
  const progress = lifetimeProgress(check);
  const days = daysRemaining(check);

  if (progress === null || days === null) {
    return (
      <div className="flex h-9 items-center font-mono text-[11px] text-faint">
        Sin certificado legible
      </div>
    );
  }

  const expired = days < 0;
  const tone = expired ? "fail" : days < 7 ? "hot" : days < 30 ? "warm" : "cool";
  const percent = Math.round(progress * 100);

  return (
    <div className="space-y-1.5">
      <div
        className="relative h-1.5 overflow-hidden rounded-full bg-line"
        role="img"
        aria-label={
          expired
            ? `Certificado vencido hace ${Math.abs(days)} días`
            : `Certificado válido ${days} días más`
        }
      >
        {/* Porción de vigencia ya transcurrida. */}
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-500"
          style={{
            width: `${percent}%`,
            background: `color-mix(in oklab, var(--color-${tone}) 55%, transparent)`,
          }}
        />
        {/* Hoy. El punto entero del componente. */}
        <div
          className="absolute inset-y-[-3px] w-[2px] rounded-full"
          style={{
            left: `calc(${percent}% - 1px)`,
            background: `var(--color-${tone})`,
            boxShadow: `0 0 8px color-mix(in oklab, var(--color-${tone}) 60%, transparent)`,
          }}
        />
      </div>

      <div className="tnum flex items-baseline justify-between font-mono text-[10.5px]">
        <span className="text-faint">{formatDate(check?.not_before ?? null)}</span>
        <span style={{ color: `var(--color-${tone})` }}>
          {expired ? `vencido hace ${Math.abs(days)} d` : `${days} d restantes`}
        </span>
        <span className="text-faint">{formatDate(check?.not_after ?? null)}</span>
      </div>
    </div>
  );
}

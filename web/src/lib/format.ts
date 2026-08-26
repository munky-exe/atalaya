import type { Check, Severity } from "../types";

/** Único lugar donde una nota se traduce a color. */
export function gradeTone(grade: string): string {
  switch (grade) {
    case "A":
      return "cool";
    case "B":
      return "mild";
    case "C":
      return "warm";
    case "D":
    case "E":
      return "hot";
    default:
      return "fail";
  }
}

export function severityTone(severity: Severity): string {
  switch (severity) {
    case "critical":
      return "fail";
    case "high":
      return "hot";
    case "medium":
      return "warm";
    case "low":
      return "mild";
    default:
      return "muted";
  }
}

export function daysRemaining(check: Check | null): number | null {
  if (!check?.not_after) return null;
  return Math.floor((new Date(check.not_after).getTime() - Date.now()) / 86_400_000);
}

/**
 * Qué fracción de su vigencia lleva recorrida el certificado, de 0 a 1.
 * Es el dato que ninguna otra herramienta muestra, y el que da sentido a
 * los días restantes: 38 sobre 89 es rutina, 38 sobre 730 es urgencia.
 */
export function lifetimeProgress(check: Check | null): number | null {
  if (!check?.not_after || !check?.not_before) return null;
  const start = new Date(check.not_before).getTime();
  const end = new Date(check.not_after).getTime();
  if (end <= start) return null;
  return Math.min(1, Math.max(0, (Date.now() - start) / (end - start)));
}

export function relativeTime(iso: string): string {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "hace un momento";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  return `hace ${Math.round(hours / 24)} d`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

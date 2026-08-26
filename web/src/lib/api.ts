import type { Check, Domain } from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Lleva el mensaje que la API envió, para mostrarlo tal cual. */
export class ApiError extends Error {
  readonly status: number;

  // El campo se declara y se asigna a mano en lugar de usar una parameter
  // property (`constructor(readonly status: number)`). Esa forma emite
  // código, y el proyecto tiene erasableSyntaxOnly: solo se permite
  // sintaxis que desaparezca al quitar los tipos.
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    // fetch solo rechaza por fallo de red; un 500 sí resuelve.
    throw new ApiError("No hay conexion con la API. Esta corriendo?", 0);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(extractMessage(body) ?? `Error ${response.status}`, response.status);
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

/**
 * FastAPI usa dos formas para `detail`: una cadena en HTTPException y una
 * lista en errores de validacion. Hay que manejar ambas o el usuario ve
 * "[object Object]" en lugar del mensaje que escribimos con cuidado.
 */
function extractMessage(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;

  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string };
    return first.msg?.replace(/^Value error, /, "") ?? null;
  }

  return null;
}

export const api = {
  listDomains: () => request<Domain[]>("/api/domains"),
  addDomain: (hostname: string) =>
    request<Domain>("/api/domains", {
      method: "POST",
      body: JSON.stringify({ hostname }),
    }),
  checkNow: (id: number) => request<Check>(`/api/domains/${id}/check`, { method: "POST" }),
  history: (id: number) => request<Check[]>(`/api/domains/${id}/checks`),
  remove: (id: number) => request<void>(`/api/domains/${id}`, { method: "DELETE" }),
};
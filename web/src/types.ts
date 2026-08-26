/** Espejo de los esquemas de salida de la API. */

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface Finding {
  code: string;
  severity: Severity;
  title: string;
  detail: string;
}

export interface Check {
  id: number;
  observed_at: string;
  score: number;
  grade: string;
  reachable: boolean;
  resolved_ip: string | null;
  handshake_ms: number | null;
  protocol: string | null;
  cipher: string | null;
  cipher_bits: number | null;
  issuer: string | null;
  subject: string | null;
  not_before: string | null;
  not_after: string | null;
  findings: Finding[];
  legacy_accepted: string[];
  legacy_untestable: string[];
  error: string | null;
}

export interface Domain {
  id: number;
  hostname: string;
  port: number;
  label: string | null;
  created_at: string;
  latest: Check | null;
}

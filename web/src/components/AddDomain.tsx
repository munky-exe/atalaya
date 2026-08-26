import { useState } from "react";

interface Props {
  onAdd: (hostname: string) => Promise<void>;
  disabled?: boolean;
}

export function AddDomain({ onAdd, disabled }: Props) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const hostname = value.trim();
    if (!hostname || busy) return;

    setBusy(true);
    setError(null);
    try {
      await onAdd(hostname);
      setValue("");
    } catch (err) {
      // El mensaje viene de la API tal cual: ahí está el ejemplo que le
      // dice al usuario qué se esperaba.
      setError(err instanceof Error ? err.message : "No se pudo agregar.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="w-full sm:w-[420px]">
      <div className="flex gap-2">
        <input
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          disabled={disabled || busy}
          placeholder="ejemplo.com"
          aria-label="Dominio a vigilar"
          spellCheck={false}
          autoComplete="off"
          className="min-w-0 flex-1 rounded-md border border-line bg-surface px-3 py-2
                     font-mono text-[13px] transition-colors placeholder:text-faint
                     focus:border-line-bright focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={submit}
          disabled={disabled || busy || !value.trim()}
          className="whitespace-nowrap rounded-md border border-line-bright bg-raised
                     px-4 py-2 text-[13px] font-medium transition-colors
                     hover:bg-line disabled:opacity-40 disabled:hover:bg-raised"
        >
          {busy ? "Revisando…" : "Vigilar"}
        </button>
      </div>

      {error && (
        <p className="mt-2 text-[12px]" style={{ color: "var(--color-fail)" }} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

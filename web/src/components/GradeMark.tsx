import { gradeTone } from "../lib/format";

/** La letra como elemento de display, no como insignia. */
export function GradeMark({ grade, score }: { grade: string; score: number }) {
  return (
    <div className="flex items-baseline gap-2">
      <span
        className="text-[34px] font-bold leading-none tracking-tight"
        style={{ color: `var(--color-${gradeTone(grade)})` }}
      >
        {grade}
      </span>
      <span className="tnum font-mono text-[11px] text-faint">{score}/100</span>
    </div>
  );
}

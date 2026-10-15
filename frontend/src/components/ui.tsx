import type { ReactNode } from "react";

export function Card({ title, subtitle, children, actions }:
  { title?: ReactNode; subtitle?: ReactNode; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p className="muted">{subtitle}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

/** A single headline number with its unit/context and where it came from. */
export function Stat({ label, value, detail, tone }:
  { label: string; value: ReactNode; detail?: ReactNode; tone?: "good" | "critical" | "warning" }) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {detail && <div className="stat-detail">{detail}</div>}
    </div>
  );
}

export type Provenance = { kind: "measured" | "price" | "assumption"; text: string } | { kind: "input" };

/** A numeric input that says whether its default was measured or assumed. */
export function NumberField({ label, value, onChange, step, min, max, suffix, prov }: {
  label: string; value: number; onChange: (v: number) => void; step?: number; min?: number; max?: number;
  suffix?: string; prov?: Provenance;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <span className="field-input">
        <input type="number" value={Number.isFinite(value) ? value : ""} step={step ?? "any"} min={min} max={max}
               onChange={(e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v)) onChange(v); }} />
        {suffix && <span className="suffix">{suffix}</span>}
      </span>
      {prov && prov.kind !== "input" && (
        <span className={`prov prov-${prov.kind}`} title={prov.text}>
          {prov.kind} · {prov.text}
        </span>
      )}
    </label>
  );
}

export function Slider({ label, value, onChange, min, max, step, format }: {
  label: string; value: number; onChange: (v: number) => void; min: number; max: number; step: number;
  format: (v: number) => string;
}) {
  return (
    <label className="field slider">
      <span className="field-label">{label} <b>{format(value)}</b></span>
      <input type="range" min={min} max={max} step={step} value={value}
             onChange={(e) => onChange(parseFloat(e.target.value))} />
    </label>
  );
}

export function Skeleton({ height = 120 }: { height?: number }) {
  return <div className="skeleton" style={{ height }} aria-busy="true" aria-label="Loading" />;
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="alert alert-critical" role="alert">
      <span aria-hidden="true">⚠</span>
      <div>
        <b>Something went wrong.</b> {error instanceof Error ? error.message : String(error)}
        {onRetry && <> <button className="link" onClick={onRetry}>Retry</button></>}
      </div>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <b>{title}</b>
      {children && <p className="muted">{children}</p>}
    </div>
  );
}

export function Badge({ tone, children }: { tone: "good" | "critical" | "warning" | "neutral"; children: ReactNode }) {
  const icon = { good: "✓", critical: "✕", warning: "!", neutral: "•" }[tone];
  return <span className={`badge badge-${tone}`}><span aria-hidden="true">{icon}</span> {children}</span>;
}

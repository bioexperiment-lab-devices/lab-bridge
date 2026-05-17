import {
  CSSProperties,
  MouseEvent,
  ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

// ----- Button -----

type ButtonVariant = "default" | "primary" | "danger" | "ghost";

interface FlButtonProps {
  variant?: ButtonVariant;
  small?: boolean;
  disabled?: boolean;
  leading?: ReactNode;
  children?: ReactNode;
  title?: string;
  type?: "button" | "submit" | "reset";
  onClick?: (e: MouseEvent<HTMLButtonElement>) => void;
  style?: CSSProperties;
}

export function FlButton({
  variant = "default",
  small,
  disabled,
  leading,
  children,
  title,
  type = "button",
  onClick,
  style,
}: FlButtonProps) {
  const cls = [
    "shp-btn",
    variant === "primary" && "shp-btn--primary",
    variant === "danger" && "shp-btn--danger",
    variant === "ghost" && "shp-btn--ghost",
    small && "shp-btn--sm",
  ].filter(Boolean).join(" ");
  return (
    <button
      type={type}
      className={cls}
      disabled={disabled}
      onClick={onClick}
      title={title}
      style={style}
    >
      {leading}
      {children}
    </button>
  );
}

// ----- Segmented control -----

interface SegOption<T extends string> { value: T; label: string; }

export function FlSeg<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: SegOption<T>[];
  onChange?: (v: T) => void;
}) {
  return (
    <div className="fl-seg">
      {options.map(o => (
        <button
          key={o.value}
          type="button"
          className="fl-seg__btn"
          data-active={o.value === value}
          onClick={() => onChange?.(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ----- Switch -----

export function FlSwitch({
  on,
  onChange,
}: {
  on: boolean;
  onChange?: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      className="fl-switch"
      data-on={on}
      role="switch"
      aria-checked={on}
      onClick={() => onChange?.(!on)}
    />
  );
}

export function FlToggleLabel({
  on,
  label,
  onChange,
}: {
  on: boolean;
  label: string;
  onChange?: (next: boolean) => void;
}) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <FlSwitch on={on} onChange={onChange} />
      <span style={{
        fontSize: 12.5,
        fontWeight: 500,
        color: on ? "var(--text)" : "var(--text-muted)",
      }}>{label}</span>
    </span>
  );
}

// ----- Tag chip -----

// Deterministic, well-spread hue from a string (djb2). Same name → same color.
export function hashHue(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return ((h % 360) + 360) % 360;
}

export function FlTag({
  name,
  selected,
  removable,
  onClick,
  onRemove,
}: {
  name: string;
  selected?: boolean;
  removable?: boolean;
  onClick?: () => void;
  onRemove?: () => void;
}) {
  return (
    <span
      className="fl-tag"
      data-selected={selected || undefined}
      style={{ ["--tag-h" as string]: hashHue(name) } as CSSProperties}
      onClick={onClick}
      role={onClick ? "button" : undefined}
    >
      {name}
      {removable && onRemove ? (
        <button
          type="button"
          className="fl-tag__x"
          aria-label={`Remove ${name}`}
          onClick={e => { e.stopPropagation(); onRemove(); }}
        >×</button>
      ) : null}
    </span>
  );
}

// ----- Outcome badge (full + compact) -----

export type Tone = "green" | "amber" | "red" | "blue" | undefined;

export function outcomeTone(outcome: string | null | undefined, status?: string): Tone {
  const value = outcome ?? status ?? "";
  if (value === "success") return "green";
  if (value === "running") return "blue";
  if (value === "failed_no_recovery" || value === "error") return "red";
  if (!value) return undefined;
  return "amber";
}

export function FlOutcome({ outcome, tone }: { outcome: string; tone?: Tone }) {
  return (
    <span className="fl-outcome" data-tone={tone}>
      <span className="fl-outcome__dot" />
      {outcome}
    </span>
  );
}

export function FlOutc({ outcome, tone }: { outcome: string; tone?: Tone }) {
  return <span className="fl-outc" data-tone={tone}>{outcome}</span>;
}

// ----- Stage strip -----

export const STAGE_ORDER = [
  "preflight",
  "backup",
  "erase",
  "program",
  "verify",
  "test",
  "rollback",
] as const;

export type StageName = typeof STAGE_ORDER[number];
export type StageState = "ok" | "failed" | "skipped" | "na" | "active";

export function FlStageStrip({ states }: { states: Partial<Record<StageName, StageState>> }) {
  return (
    <div className="fl-stage">
      {STAGE_ORDER.map(s => (
        <span
          key={s}
          className="fl-stage__chip"
          data-state={states[s] ?? "na"}
          title={`${s}: ${states[s] ?? "n/a"}`}
        >
          {s}
        </span>
      ))}
    </div>
  );
}

// ----- Hex input (readonly display + bytes/ascii) -----

export function FlHexInput({
  label,
  value,
  bytes,
  ascii,
  error,
  labelWidth = 130,
  onChange,
  editable = false,
  placeholder,
}: {
  label: string;
  value: string;
  bytes: number;
  ascii?: string;
  error?: boolean;
  labelWidth?: number;
  onChange?: (next: string) => void;
  editable?: boolean;
  placeholder?: string;
}) {
  return (
    <div className="fl-hex">
      <div className="fl-hex__row" style={{ gridTemplateColumns: `${labelWidth}px minmax(0, 1fr)` }}>
        <span className="fl-hex__label">{label}</span>
        <input
          className="fl-hex__input"
          value={value}
          data-error={error || undefined}
          readOnly={!editable}
          placeholder={placeholder}
          onChange={onChange ? (e) => onChange(e.target.value) : undefined}
          spellCheck={false}
          autoComplete="off"
        />
      </div>
      <div className="fl-hex__meta" style={{ paddingLeft: labelWidth + 10 }}>
        {error
          ? <span className="fl-hex__meta--err">invalid hex</span>
          : <span><b>{bytes}</b> bytes</span>}
        {!error && ascii != null && ascii.length > 0 && (
          <span>ASCII: <b>"{ascii}"</b></span>
        )}
      </div>
    </div>
  );
}

// ----- Hex diff -----

export function FlHexDiff({
  expected,
  received,
  diffIdx = [],
}: {
  expected: string[];
  received: string[];
  diffIdx?: number[];
}) {
  const diffSet = new Set(diffIdx);
  const renderRow = (bytes: string[], role: string) => (
    <div className="fl-diff__row">
      <div className="fl-diff__lbl">{role}</div>
      <div className="fl-diff__bytes">
        {bytes.length === 0 ? <span className="shp-dim">—</span> : bytes.map((b, i) => (
          <span key={i} className="fl-diff__byte" data-diff={diffSet.has(i) || undefined}>{b}</span>
        ))}
      </div>
    </div>
  );
  const matches = diffIdx.length === 0;
  return (
    <div className="fl-diff">
      {renderRow(expected, "Expected")}
      {renderRow(received, "Received")}
      <div className={"fl-diff__foot" + (matches ? "" : " fl-diff__foot--err")}>
        <span>{matches ? "Byte-for-byte match." : `${diffIdx.length} byte(s) differ.`}</span>
        <span className="fl-muted">{Math.max(expected.length, received.length)} bytes total</span>
      </div>
    </div>
  );
}

// ----- Stats card -----

export function FlStatsCard({
  total,
  successes,
  rollbacks,
  failures,
  lastFlashed,
}: {
  total: number;
  successes: number;
  rollbacks: number;
  failures: number;
  lastFlashed?: string | null;
}) {
  const pct = total > 0 ? Math.round((successes / total) * 100) : null;
  return (
    <div className="fl-stats">
      <span className="fl-stat__lbl">Total flashes</span>
      <span className="fl-stat__val">{total}</span>
      <span className="fl-muted fl-mono" style={{ fontSize: 11 }}>
        success {successes} · rolled {rollbacks} · failed {failures}
        {pct != null && <> · {pct}%</>}
      </span>
      {lastFlashed && (
        <span className="fl-stat__sub">last · {lastFlashed}</span>
      )}
    </div>
  );
}

// ----- JSON renderer -----

export function FlJSON({ data }: { data: unknown }) {
  const json = JSON.stringify(data, null, 2);
  const html = json
    .replace(/[&<>]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch] as string))
    .replace(/(&quot;(?:[^&\\]|\\.)*?&quot;)(\s*:)/g, '<span class="fl-json-k">$1</span>$2')
    .replace(/("(?:[^"\\]|\\.)*?")(\s*:)/g, '<span class="fl-json-k">$1</span>$2')
    .replace(/:\s*("(?:[^"\\]|\\.)*?")/g, (m, s) => m.replace(s, `<span class="fl-json-s">${s}</span>`))
    .replace(/:\s*(-?\d+(?:\.\d+)?)/g, (m, n) => m.replace(n, `<span class="fl-json-n">${n}</span>`))
    .replace(/:\s*(true|false|null)/g, (m, b) => m.replace(b, `<span class="fl-json-b">${b}</span>`));
  return <pre dangerouslySetInnerHTML={{ __html: html }} />;
}

// ----- Dropdown -----

export interface FlOption<V extends string = string> {
  value: V;
  label: string;
  disabled?: boolean;
}

export function FlDropdown<V extends string = string>({
  value,
  options,
  placeholder = "(select…)",
  width,
  mono,
  onChange,
  disabled,
}: {
  value: V | "";
  options: FlOption<V>[];
  placeholder?: string;
  width?: number | string;
  mono?: boolean;
  onChange?: (v: V) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const pos = useFixedAnchor(open, triggerRef);
  useFloatingClose(open, () => setOpen(false), [triggerRef, panelRef]);
  const current = options.find(o => o.value === value);
  const monoStyle: CSSProperties | undefined = mono
    ? { fontFamily: "'IBM Plex Mono', monospace", fontSize: 12 }
    : undefined;
  return (
    <div className="fl-dd" style={width ? { width, maxWidth: "100%" } : undefined}>
      <button
        ref={triggerRef}
        type="button"
        className="fl-dd__btn"
        data-open={open || undefined}
        data-placeholder={(!current) || undefined}
        style={monoStyle}
        disabled={disabled}
        onClick={() => setOpen(o => !o)}
      >
        <span className="fl-dd__label">{current ? current.label : placeholder}</span>
      </button>
      {open && pos && createPortal(
        <div
          ref={panelRef}
          className="fl-dd__panel"
          style={{ position: "fixed", top: pos.top, left: pos.left, minWidth: pos.width }}
        >
          {options.map(o => (
            <div
              key={o.value}
              className="fl-dd__opt"
              data-active={o.value === value || undefined}
              data-disabled={o.disabled || undefined}
              style={monoStyle}
              onClick={() => {
                if (o.disabled) return;
                onChange?.(o.value);
                setOpen(false);
              }}
            >
              <span>{o.label}</span>
              {o.value === value && <span className="fl-dd__check">✓</span>}
            </div>
          ))}
        </div>,
        document.body,
      )}
    </div>
  );
}

// ----- Floating-panel helpers -----

interface AnchorPos { top: number; left: number; width: number; }

function useFixedAnchor(open: boolean, triggerRef: React.RefObject<HTMLElement>): AnchorPos | null {
  const [pos, setPos] = useState<AnchorPos | null>(null);
  useEffect(() => {
    if (!open || !triggerRef.current) { setPos(null); return; }
    const update = () => {
      const el = triggerRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      setPos({ top: Math.round(r.bottom + 4), left: Math.round(r.left), width: Math.round(r.width) });
    };
    update();
    window.addEventListener("resize", update);
    // Capture so scrolls in nested overflow containers also fire.
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, triggerRef]);
  return pos;
}

function useFloatingClose(
  open: boolean,
  close: () => void,
  refs: React.RefObject<HTMLElement>[],
) {
  useEffect(() => {
    if (!open) return;
    const onDown = (e: globalThis.MouseEvent) => {
      const t = e.target as Node;
      for (const r of refs) {
        if (r.current && r.current.contains(t)) return;
      }
      close();
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
}

// ----- Date input -----

export function FlDateInput({
  value,
  onChange,
}: {
  value: string;
  onChange?: (next: string) => void;
}) {
  return (
    <input
      type="date"
      className="fl-date"
      value={value}
      onChange={e => onChange?.(e.target.value)}
    />
  );
}

// ----- Badge multi-select with add-dropdown -----

export function FlBadgeMulti({
  selected = [],
  options = [],
  onAdd,
  onRemove,
  addLabel = "Add",
  emptyLabel = "(none)",
  colorize = false,
  mono = false,
  bare = false,
}: {
  selected: string[];
  options: FlOption[];
  onAdd?: (v: string) => void;
  onRemove?: (v: string) => void;
  addLabel?: string;
  emptyLabel?: string;
  /** When true, each badge is tinted by a hue hashed from its label. */
  colorize?: boolean;
  mono?: boolean;
  bare?: boolean;
}) {
  const labelOf = (v: string) => options.find(o => o.value === v)?.label ?? v;
  const available = options.filter(o => !selected.includes(o.value));
  return (
    <div className={"fl-multi" + (bare ? " fl-multi--bare" : "")}>
      {selected.length === 0 && <span className="fl-multi__empty">{emptyLabel}</span>}
      {selected.map(v => {
        const lbl = labelOf(v);
        const tinted = colorize
          ? ({ ["--tag-h" as string]: hashHue(lbl) } as CSSProperties)
          : undefined;
        return (
          <span
            key={v}
            className={"fl-multi__badge" + (mono ? " fl-multi__badge--mono" : "")}
            data-colored={colorize || undefined}
            style={tinted}
          >
            <span>{lbl}</span>
            <button
              type="button"
              className="fl-multi__x"
              onClick={() => onRemove?.(v)}
              aria-label={`Remove ${lbl}`}
            >×</button>
          </span>
        );
      })}
      <FlBadgeMultiAdder
        addLabel={addLabel}
        options={available}
        mono={mono}
        onAdd={v => onAdd?.(v)}
      />
    </div>
  );
}

function FlBadgeMultiAdder({
  addLabel,
  options,
  mono,
  onAdd,
}: {
  addLabel: string;
  options: FlOption[];
  mono: boolean;
  onAdd: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const pos = useFixedAnchor(open, triggerRef);
  useFloatingClose(open, () => setOpen(false), [triggerRef, panelRef]);
  const monoStyle: CSSProperties | undefined = mono
    ? { fontFamily: "'IBM Plex Mono', monospace", fontSize: 12 }
    : undefined;
  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="fl-multi__add"
        onClick={() => setOpen(o => !o)}
        disabled={options.length === 0}
      >
        <span className="fl-multi__add__plus">+</span>
        <span>{addLabel}</span>
      </button>
      {open && options.length > 0 && pos && createPortal(
        <div
          ref={panelRef}
          className="fl-dd__panel"
          style={{ position: "fixed", top: pos.top, left: pos.left, minWidth: Math.max(180, pos.width) }}
        >
          {options.map(o => (
            <div
              key={o.value}
              className="fl-dd__opt"
              style={monoStyle}
              onClick={() => { onAdd(o.value); setOpen(false); }}
            >
              <span>{o.label}</span>
            </div>
          ))}
        </div>,
        document.body,
      )}
    </>
  );
}

// ----- Page header wrapper -----

export function FlPage({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="fl-page">
      {(title || actions) && (
        <header className="fl-page__head">
          <div>
            <h1 className="fl-page__title">{title}</h1>
            {subtitle && <div className="fl-page__sub">{subtitle}</div>}
          </div>
          {actions && <div className="fl-page__actions">{actions}</div>}
        </header>
      )}
      {children}
    </div>
  );
}

// ----- Step section -----

export function FlStep({
  num,
  title,
  sub,
  state = "active",
  actions,
  children,
}: {
  num: number;
  title: string;
  sub?: ReactNode;
  state?: "done" | "active" | "pending";
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="fl-step" data-state={state}>
      <div className="fl-step__head">
        <span className="fl-step__num">{num}</span>
        <span className="fl-step__title">{title}</span>
        {sub != null && <span className="fl-step__sub">{sub}</span>}
        {actions && <div className="fl-step__actions">{actions}</div>}
      </div>
      <div className="fl-step__body">{children}</div>
    </section>
  );
}

// ----- Modal scrim wrapper -----

export function FlModal({
  width = 480,
  title,
  subtitle,
  onClose,
  footer,
  children,
}: {
  width?: number;
  title: string;
  subtitle?: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  children?: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="shp-modal-scrim" onMouseDown={onClose}>
      <div
        className="shp-modal"
        style={{ width }}
        onMouseDown={e => e.stopPropagation()}
      >
        <div className="shp-modal__head">
          <h3 className="shp-modal__title">{title}</h3>
          {subtitle && <div className="shp-modal__sub">{subtitle}</div>}
        </div>
        <div className="shp-modal__body">{children}</div>
        {footer && <div className="shp-modal__foot">{footer}</div>}
      </div>
    </div>
  );
}

"use client";

import React from "react";

/* ------------------------------------------------------------------ */
/*  V3 Tag — inline status tag with tone variants                     */
/* ------------------------------------------------------------------ */

type V3TagTone = "ok" | "warn" | "err" | "fill" | "acc";

interface V3TagProps {
  tone?: V3TagTone;
  children: React.ReactNode;
}

export function V3Tag({ tone, children }: V3TagProps) {
  return (
    <span className="v3-tag" data-tone={tone}>
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  V3 Brk — bracket-wrapped text [content]                           */
/* ------------------------------------------------------------------ */

interface V3BrkProps {
  children: React.ReactNode;
}

export function V3Brk({ children }: V3BrkProps) {
  return (
    <span className="v3-brk">
      [<span style={{ color: "var(--ink)" }}>{children}</span>]
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  V3 TitleBar — terminal titlebar with dots + path + right slot     */
/* ------------------------------------------------------------------ */

interface V3TitleBarProps {
  path?: string;
  right?: React.ReactNode;
}

export function V3TitleBar({
  path = "engram@core:~$",
  right,
}: V3TitleBarProps) {
  return (
    <div className="v3-titlebar">
      <span className="dot" />
      <span className="dot" style={{ opacity: 0.6 }} />
      <span className="dot" style={{ opacity: 0.3 }} />
      <span style={{ marginLeft: 8 }}>{path}</span>
      <span style={{ flex: 1 }} />
      {right}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  V3 StatusBar — bottom status bar with pipe-separated items        */
/* ------------------------------------------------------------------ */

interface V3StatusBarProps {
  items: React.ReactNode[];
}

export function V3StatusBar({ items }: V3StatusBarProps) {
  return (
    <div className="v3-statusbar">
      {items.map((item, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span style={{ color: "var(--ink-4)" }}>{"\u2502"}</span>}
          <span>{item}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  V3 Btn — bracket-style button [ label ]                           */
/* ------------------------------------------------------------------ */

type V3BtnVariant = "acc" | "ghost";
type V3BtnSize = "sm";

interface V3BtnProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: V3BtnVariant;
  size?: V3BtnSize;
  children: React.ReactNode;
}

export function V3Btn({ variant, size, children, ...rest }: V3BtnProps) {
  return (
    <button
      className="v3-btn"
      data-variant={variant}
      data-size={size}
      {...rest}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  V3 Input — terminal-style input                                   */
/* ------------------------------------------------------------------ */

export function V3Input({ style, ...rest }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className="v3-input" style={style} {...rest} />;
}

/* ------------------------------------------------------------------ */
/*  V3 Hr — dotted ASCII horizontal rule                              */
/* ------------------------------------------------------------------ */

export function V3Hr() {
  return <hr className="v3-hr" />;
}

/* ------------------------------------------------------------------ */
/*  V3 BigNum — large tabular number display                          */
/* ------------------------------------------------------------------ */

interface V3BigNumProps {
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export function V3BigNum({ children, style }: V3BigNumProps) {
  return (
    <span className="v3-bignum" style={style}>
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  V3 Meter — spark/meter dot bars                                   */
/* ------------------------------------------------------------------ */

interface V3MeterProps {
  /** Array of bar heights (0-10 px each) */
  bars: number[];
  color?: string;
}

export function V3Meter({ bars, color }: V3MeterProps) {
  return (
    <span className="v3-meter">
      {bars.map((h, i) => (
        <i
          key={i}
          style={{
            height: h,
            background: color ?? "var(--ink)",
          }}
        />
      ))}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  V3 Kbd — inline keyboard shortcut                                 */
/* ------------------------------------------------------------------ */

interface V3KbdProps {
  children: React.ReactNode;
}

export function V3Kbd({ children }: V3KbdProps) {
  return <kbd className="v3-kbd">{children}</kbd>;
}

/* ------------------------------------------------------------------ */
/*  EgLogo — v3 style: square box + accent inner square               */
/* ------------------------------------------------------------------ */

interface EgLogoProps {
  size?: number;
}

export function EgLogo({ size = 14 }: EgLogoProps) {
  const inner = Math.round(size * 0.43);
  const offset = Math.round((size - inner) / 2);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <rect
        x="0.5"
        y="0.5"
        width={size - 1}
        height={size - 1}
        fill="none"
        stroke="var(--ink)"
      />
      <rect
        x={offset}
        y={offset}
        width={inner}
        height={inner}
        fill="var(--accent)"
      />
    </svg>
  );
}

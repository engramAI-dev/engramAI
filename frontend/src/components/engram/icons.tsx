/* Engram icons — line, 16px viewBox, currentColor. */

import React from "react";

interface IconBaseProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

interface IconSvgProps {
  d: React.ReactNode;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
  stroke?: number;
  fill?: string;
  viewBox?: string;
}

function IconSvg({
  d,
  size = 16,
  stroke = 1.5,
  fill = "none",
  viewBox = "0 0 16 16",
  className,
  style,
}: IconSvgProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox={viewBox}
      fill={fill}
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden="true"
    >
      {typeof d === "string" ? <path d={d} /> : d}
    </svg>
  );
}

export function Logo({ size = 16, className, style }: IconBaseProps) {
  return (
    <IconSvg
      size={size}
      className={className}
      style={style}
      d={
        <g>
          <rect x="2" y="2" width="12" height="12" rx="2.5" fill="currentColor" stroke="none" />
          <circle cx="8" cy="8" r="2.4" fill="var(--bg)" stroke="none" />
        </g>
      }
    />
  );
}

export function Chat({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M2.5 4.5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H7l-3 2.5v-2.5h-.5a1 1 0 0 1-1-1z" />;
}

export function Plug({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M5 2v3M11 2v3M3.5 5h9v3a4.5 4.5 0 1 1-9 0zM8 13.5V15" />;
}

export function Library({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M3 3h3v10H3zM7 3h3v10H7zM10.5 4.5l2.4-.6 2 9.7-2.4.6z" />;
}

export function Jobs({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M2.5 4.5h11M2.5 8h11M2.5 11.5h7" />;
}

export function Out({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M3 3h7l3 3v7a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM10 3v3h3M5 9h6M5 11.5h4" />;
}

export function Compare({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M8 1.5v13M3 4l-1.5 1.5L3 7M13 9l1.5 1.5L13 12" />;
}

export function Settings({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM8 1.5v2M8 12.5v2M3.5 8h-2M14.5 8h-2M4.5 4.5l-1.4-1.4M12.9 12.9l-1.4-1.4M4.5 11.5l-1.4 1.4M12.9 3.1l-1.4 1.4" />;
}

export function Search({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M7 12.5a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11zM11 11l3 3" />;
}

export function Plus({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M8 3v10M3 8h10" />;
}

export function Check({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M3 8.5l3 3 7-7" />;
}

export function X({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M3.5 3.5l9 9M12.5 3.5l-9 9" />;
}

export function ChevronR({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M6 3.5l4.5 4.5L6 12.5" />;
}

export function ChevronD({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M3.5 6L8 10.5 12.5 6" />;
}

export function ChevronL({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M10 3.5L5.5 8 10 12.5" />;
}

export function Arrow({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M3 8h10M9.5 4.5L13 8l-3.5 3.5" />;
}

export function ArrowUp({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M8 13V3M4 6.5L8 3l4 3.5" />;
}

export function DotIcon({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M8 8h.01" stroke={4} />;
}

export function More({ size = 16, className, style }: IconBaseProps) {
  return (
    <IconSvg
      size={size}
      className={className}
      style={style}
      d={
        <g>
          <circle cx="3.5" cy="8" r="1" fill="currentColor" stroke="none" />
          <circle cx="8" cy="8" r="1" fill="currentColor" stroke="none" />
          <circle cx="12.5" cy="8" r="1" fill="currentColor" stroke="none" />
        </g>
      }
    />
  );
}

export function GitHub({ size = 16, className, style }: IconBaseProps) {
  return (
    <IconSvg
      size={size}
      className={className}
      style={style}
      fill="currentColor"
      stroke={0}
      d={
        <path d="M8 .8a7.2 7.2 0 0 0-2.28 14.04c.36.07.5-.16.5-.35v-1.22c-2 .43-2.43-.97-2.43-.97-.33-.83-.8-1.05-.8-1.05-.66-.45.05-.44.05-.44.73.05 1.11.75 1.11.75.65 1.11 1.7.79 2.11.6.07-.47.25-.79.46-.97-1.6-.18-3.28-.8-3.28-3.56 0-.79.28-1.43.74-1.93-.07-.18-.32-.92.07-1.92 0 0 .6-.19 1.97.74A6.86 6.86 0 0 1 8 4.46c.6 0 1.22.08 1.79.24 1.36-.93 1.96-.74 1.96-.74.4 1 .15 1.74.07 1.92.46.5.74 1.14.74 1.93 0 2.77-1.69 3.38-3.29 3.55.26.22.49.66.49 1.33v1.97c0 .19.13.42.5.35A7.2 7.2 0 0 0 8 .8z" />
      }
    />
  );
}

export function Notion({ size = 16, className, style }: IconBaseProps) {
  return (
    <IconSvg
      size={size}
      className={className}
      style={style}
      d={
        <g>
          <rect x="2.2" y="2" width="11.6" height="12" rx="1.5" fill="currentColor" stroke="none" />
          <path d="M5 5.2v5.6M5 5.2l4.5 5.6V5.2" stroke="var(--bg)" strokeWidth="1.4" fill="none" />
          <circle cx="11.5" cy="5.2" r="0.6" fill="var(--bg)" stroke="none" />
        </g>
      }
    />
  );
}

export function File({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M3.5 2h6L12.5 5v9H3.5zM9.5 2v3h3" />;
}

export function Folder({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M2 4.5a1 1 0 0 1 1-1h3l1 1.5h6a1 1 0 0 1 1 1V12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1z" />;
}

export function Refresh({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M2.5 8a5.5 5.5 0 0 1 9.6-3.7M13.5 8a5.5 5.5 0 0 1-9.6 3.7M12 2v3h-3M4 14v-3h3" />;
}

export function Trash({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M3 4.5h10M5 4.5V3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1.5M4 4.5l.6 8.5a1 1 0 0 0 1 1h4.8a1 1 0 0 0 1-1l.6-8.5" />;
}

export function Copy({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M5 5V3a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-2M3 5h7a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />;
}

export function Download({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M8 2v8M4.5 7L8 10.5 11.5 7M3 13h10" />;
}

export function Link({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M7 9a2.5 2.5 0 0 0 3.5 0l2-2a2.5 2.5 0 0 0-3.5-3.5L7.5 4.5M9 7a2.5 2.5 0 0 0-3.5 0l-2 2A2.5 2.5 0 0 0 7 12.5L8.5 11" />;
}

export function Eye({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z M8 6a2 2 0 1 0 0 4 2 2 0 0 0 0-4z" />;
}

export function Filter({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M2 3.5h12L9.5 8.5v4l-3 1V8.5z" />;
}

export function Sun({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M8 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM8 1.5v1.8M8 12.7v1.8M2.8 2.8l1.3 1.3M11.9 11.9l1.3 1.3M1.5 8h1.8M12.7 8h1.8M2.8 13.2l1.3-1.3M11.9 4.1l1.3-1.3" />;
}

export function Moon({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M13 9.5A5.5 5.5 0 1 1 6.5 3a4.5 4.5 0 0 0 6.5 6.5z" />;
}

export function Code({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M5.5 4.5L2 8l3.5 3.5M10.5 4.5L14 8l-3.5 3.5M9.5 3l-3 10" />;
}

export function Doc({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M3.5 2h7L13 4.5V14H3.5zM5.5 7h5M5.5 9.5h5M5.5 12h3" />;
}

export function Stale({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M8 2.5v3l2 2M8 14.5A6.5 6.5 0 1 0 8 1.5a6.5 6.5 0 0 0 0 13z" />;
}

export function Sparkle({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M8 2v4M8 10v4M2 8h4M10 8h4" />;
}

export function Send({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M2 8L14 3l-3 11-3-5z M2 8l5.5 1" />;
}

export function Stop({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} fill="currentColor" stroke={0} d="M4 4h8v8H4z" />;
}

export function Bolt({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M9 1.5L3.5 9h4L7 14.5 12.5 7h-4z" />;
}

export function Warn({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M8 1.5L14.5 13h-13zM8 6v3M8 11.2v.05" />;
}

export function Cmd({ size = 16, className, style }: IconBaseProps) {
  return <IconSvg size={size} className={className} style={style} d="M5 5h6v6H5zM5 5V3.5a1.5 1.5 0 1 0-1.5 1.5H5zM11 5h1.5A1.5 1.5 0 1 0 11 3.5V5zM5 11v1.5a1.5 1.5 0 1 1-1.5-1.5H5zM11 11h1.5A1.5 1.5 0 1 1 11 12.5V11z" />;
}

/* ---------- I-prefixed aliases (used by app-shell components) ---------- */

export {
  Logo as ILogo,
  Chat as IChat,
  Plug as IPlug,
  Library as ILibrary,
  Jobs as IJobs,
  Out as IOut,
  Compare as ICompare,
  Settings as ISettings,
  Search as ISearch,
  Plus as IPlus,
  Check as ICheck,
  X as IX,
  ChevronR as IChevronR,
  ChevronD as IChevronD,
  ChevronL as IChevronL,
  Arrow as IArrow,
  ArrowUp as IArrowUp,
  DotIcon as IDotIcon,
  More as IMore,
  GitHub as IGitHub,
  Notion as INotion,
  File as IFile,
  Folder as IFolder,
  Refresh as IRefresh,
  Trash as ITrash,
  Copy as ICopy,
  Download as IDownload,
  Link as ILink,
  Eye as IEye,
  Filter as IFilter,
  Sun as ISun,
  Moon as IMoon,
  Code as ICode,
  Doc as IDoc,
  Stale as IStale,
  Sparkle as ISparkle,
  Send as ISend,
  Stop as IStop,
  Bolt as IBolt,
  Warn as IWarn,
  Cmd as ICmd,
};

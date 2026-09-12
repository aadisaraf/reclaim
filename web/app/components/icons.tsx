// Small inline-SVG icon set (design-system/reclaim/MASTER.md forbids emoji-as-icons).
// Kept to exactly the icons this app actually uses — no icon library dependency needed for six shapes.

type IconProps = { size?: number; className?: string };

export function CheckCircleIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <circle cx="10" cy="10" r="9" fill="var(--status-success-fg)" />
      <path d="M6 10.5l2.5 2.5L14 7.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function XCircleIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <circle cx="10" cy="10" r="9" fill="var(--color-muted-foreground)" />
      <path d="M7 7l6 6M13 7l-6 6" stroke="white" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function AlertCircleIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <circle cx="10" cy="10" r="9" fill="var(--status-attention-fg)" />
      <path d="M10 6v5" stroke="white" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="10" cy="13.5" r="1" fill="white" />
    </svg>
  );
}

export function MailIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="2.5" y="4.5" width="15" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M3.5 5.5l6.5 5 6.5-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function CopyIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="7" y="7" width="9.5" height="9.5" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4.5 12.5V4.5A1.5 1.5 0 016 3h8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function MoreIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <circle cx="4" cy="10" r="1.6" />
      <circle cx="10" cy="10" r="1.6" />
      <circle cx="16" cy="10" r="1.6" />
    </svg>
  );
}

export function DocumentStackIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="4" y="3" width="10" height="13" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M7 7h4M7 10h4M7 13h2.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

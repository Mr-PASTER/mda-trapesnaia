export function Card({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return <div className={`rounded-2xl border border-border bg-surface p-4 shadow-card ${className}`}>{children}</div>;
}

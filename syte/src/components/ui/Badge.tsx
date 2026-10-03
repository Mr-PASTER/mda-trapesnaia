export function Badge({ children, tone = "muted" }: { children: React.ReactNode; tone?: "muted" | "accent" }) {
  const styles = tone === "accent" ? "bg-accent text-on-accent" : "bg-paper text-muted border border-border";
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs ${styles}`}>{children}</span>;
}

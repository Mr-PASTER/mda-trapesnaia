import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const base =
    "inline-flex items-center justify-center rounded-xl px-4 min-h-11 text-sm font-medium transition disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
  const styles: Record<Variant, string> = {
    primary: "bg-accent text-on-accent hover:brightness-95",
    ghost: "bg-transparent text-ink border border-border hover:bg-sunken",
    danger: "bg-ink text-paper hover:brightness-105",
  };
  return <button className={`${base} ${styles[variant]} ${className}`} {...props} />;
}

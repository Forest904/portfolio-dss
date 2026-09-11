import type { ReactNode } from "react";

type NoticeProps = {
  children: ReactNode;
  kind?: "info" | "warning" | "error";
  role?: "alert" | "status";
  title?: string;
};

export function Notice({ children, kind = "info", role, title }: NoticeProps) {
  return (
    <aside className={`notice notice-${kind}`} role={role}>
      {title && <strong>{title}</strong>}
      <div>{children}</div>
    </aside>
  );
}

type SectionHeadingProps = {
  eyebrow: string;
  title: string;
  id?: string;
  children?: ReactNode;
};

export function SectionHeading({ eyebrow, title, id, children }: SectionHeadingProps) {
  return (
    <div className="section-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 id={id}>{title}</h2>
      </div>
      {children && <div className="section-heading-copy">{children}</div>}
    </div>
  );
}

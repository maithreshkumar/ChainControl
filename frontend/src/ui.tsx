import type { ReactNode } from "react";
import axios from "axios";
import { Boxes } from "lucide-react";

export function errorMessage(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.error?.message ?? error.message;
  return error instanceof Error ? error.message : "The operation failed.";
}

export function Page({ title, subtitle, action, children }: { title: string; subtitle: string; action?: ReactNode; children: ReactNode }) {
  return <main className="page"><div className="page-title"><div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>{children}</main>;
}

export function Status({ value }: { value: string }) {
  return <span className={`badge ${value.toLowerCase().replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}

export function Empty({ text }: { text: string }) {
  return <div className="empty"><Boxes size={26} /><p>{text}</p></div>;
}

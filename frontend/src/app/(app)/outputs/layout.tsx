import { Suspense, type ReactNode } from "react";

export default function OutputsLayout({ children }: { children: ReactNode }) {
  return <Suspense fallback={null}>{children}</Suspense>;
}

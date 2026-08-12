import type { Metadata } from "next";

import "./styles.css";

export const metadata: Metadata = {
  title: "Avert inventory",
  description: "External API dependencies and lifecycle risk",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

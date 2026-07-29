import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GOLD COMMAND AI",
  description: "XAUUSD AI dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="bg">
      <body>{children}</body>
    </html>
  );
}

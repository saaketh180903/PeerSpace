import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "PeerSpace",
  description: "Find people to do things with.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

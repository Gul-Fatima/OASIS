import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "OASIS — Energy-Aware Code Optimization",
    template: "%s | OASIS",
  },
  description:
    "Analyze code, explore optimization opportunities, verify correctness, and evaluate software performance and energy consumption.",
};

/**
 * Applies the stored theme before the first paint, so a light-theme user never
 * sees a dark flash. Dark is the default: with no stored value the attribute
 * stays unset and globals.css serves its dark palette.
 */
const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("oasis-theme");if(t==="light"||t==="dark"){document.documentElement.dataset.theme=t;}}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    // The inline script above sets data-theme before React hydrates, so the
    // server HTML and the client tree differ by exactly that attribute.
    // suppressHydrationWarning is scoped to <html> and only silences that
    // known difference; children are still checked normally.
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-canvas text-ink antialiased">
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        {children}
      </body>
    </html>
  );
}

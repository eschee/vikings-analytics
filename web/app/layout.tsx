import type { Metadata, Viewport } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";

/* next/font self-hosts both families at build time: no network request from
   the browser, no layout shift, and no extra dependency to vet. Each exposes a
   CSS variable that globals.css maps onto --font-display / --font-body. */
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "700"],
  variable: "--font-space-grotesk",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Hatewatch — who to root for",
  description:
    "Which results help the Vikings most, ranked by how much they move the odds.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#2b1758",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${inter.variable}`}>
      <body className="min-h-dvh antialiased">
        {/* Three sizes, mobile first:
              phone     a 480px column, centred -- the design's real layout
              sm 640px  the same single column, widened to 600px (a tablet,
                        or a Mac window snapped to half the screen, ~750px)
              lg 1024px full width: the header runs edge to edge and its
                        content, like the Guide's two columns, is centred
                        at 1180px. See Header.tsx and Guide.tsx. */}
        <div className="mx-auto w-full max-w-[480px] bg-page shadow-sm sm:max-w-[600px] lg:max-w-none lg:shadow-none">
          {children}
        </div>
      </body>
    </html>
  );
}

import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ??
      'https://shiftzero-hero-002.mingjen.chatgpt.site',
  ),
  title: 'ShiftZero HERO-002 | Judge Mode',
  description:
    'One sentence in. One verified robot mission out. A proof-carrying mission console for warehouse robots.',
  openGraph: {
    title: 'ShiftZero HERO-002 | Judge Mode',
    description: 'One sentence in. One verified robot mission out.',
    images: [{ url: '/og.png', width: 1732, height: 909 }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ShiftZero HERO-002 | Judge Mode',
    description: 'One sentence in. One verified robot mission out.',
    images: ['/og.png'],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}

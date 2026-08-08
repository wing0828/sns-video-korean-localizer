import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "말옮김 — 영상 번역을 내 컴퓨터에서",
  description: "영상 링크를 한국어 자막과 더빙으로 바꾸는 로컬 영상 번역 도구",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}

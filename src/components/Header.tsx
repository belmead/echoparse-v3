// components/Header.tsx
import React from "react";

export default function Header() {
  return (
    <header className="flex justify-between items-center mb-8">
      <h1 className="text-2xl font-mono font-light text-[#FAFAFA]">echoparse_v3</h1>
      <button className="text-[#FAFAFA] text-sm underline">Log out</button>
    </header>
  );
}

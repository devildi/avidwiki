"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Search, Monitor, Settings, Database, Brain } from 'lucide-react';
import clsx from 'clsx';

export default function Navbar() {
  const pathname = usePathname();

  const navItems = [
    {
      label: '知识搜索',
      href: '/',
      icon: Search,
    },
    {
      label: '机房监控',
      href: '/monitoring',
      icon: Monitor,
    },
    {
      label: '模型训练',
      href: '/training',
      icon: Brain,
    },
    {
      label: '系统设置',
      href: '/settings',
      icon: Settings,
    },
  ];

  return (
    <nav className="w-full sticky top-0 z-50 backdrop-blur-md bg-neutral-900/70 border-b border-neutral-800/80 px-8 py-4 flex items-center justify-between shadow-lg">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold shadow-md shadow-purple-500/20">
          A
        </div>
      </div>

      <div className="flex items-center gap-1 bg-neutral-950/40 p-1 rounded-xl border border-neutral-800/40">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "relative flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 active:scale-95 overflow-hidden",
                isActive
                  ? "bg-gradient-to-r from-purple-600/90 to-pink-600/90 text-white shadow-md shadow-purple-500/10"
                  : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50"
              )}
            >
              <Icon size={16} className={clsx(isActive ? "text-white" : "text-neutral-400 group-hover:text-neutral-200")} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>

      <div className="hidden md:flex items-center gap-2 text-xs text-neutral-500 font-mono">
        <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></span>
        <span>System Online</span>
      </div>
    </nav>
  );
}

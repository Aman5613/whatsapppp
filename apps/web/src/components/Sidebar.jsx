import React, { useState, useEffect } from 'react';
import {
  IconBot,
  IconChat,
  IconInbox,
  IconProduct,
  IconOrder,
  IconAnalytics,
  IconSettings,
  IconLogout,
  IconClose,
  IconChevronLeft,
} from './Icons';

export default function Sidebar({
  activeTab,
  setActiveTab,
  business,
  user,
  onLogout,
  mobileOpen = false,
  setMobileOpen = () => {},
  sidebarCollapsed = false,
  onToggleCollapse = () => {},
}) {
  const [handoffCount, setHandoffCount] = useState(0);

  useEffect(() => {
    if (!business?.id) return;
    const fetchCount = async () => {
      try {
        const res = await fetch(`/api/handoff?business_id=${business.id}`);
        if (res.ok) {
          const data = await res.json();
          setHandoffCount(data.length);
        }
      } catch {
        // ignore
      }
    };
    fetchCount();

    // Update on real-time SSE events
    const onRealtimeEvent = () => fetchCount();
    window.addEventListener('app-realtime-event', onRealtimeEvent);
    window.addEventListener('focus', onRealtimeEvent);

    // 60-second background fallback
    const interval = setInterval(fetchCount, 60000);
    return () => {
      clearInterval(interval);
      window.removeEventListener('app-realtime-event', onRealtimeEvent);
      window.removeEventListener('focus', onRealtimeEvent);
    };
  }, [business?.id]);

  const navItems = [
    { id: 'conversations', label: 'Conversations', icon: IconChat },
    { id: 'handoff', label: 'Handoff Inbox', icon: IconInbox, badge: handoffCount },
    { id: 'products', label: 'Products', icon: IconProduct },
    { id: 'orders', label: 'Orders', icon: IconOrder },
    { id: 'usage', label: 'Usage & Cost', icon: IconAnalytics },
    { id: 'settings', label: 'Settings', icon: IconSettings },
  ];

  const handleSelectTab = (tabId) => {
    setActiveTab(tabId);
    setMobileOpen(false);
  };

  const sidebarContent = (
    <>
      <div>
        {/* Brand header */}
        <div className="p-5 sm:p-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400 shadow-md shadow-brand-500/10 shrink-0">
              <IconBot className="w-6 h-6" />
            </div>
            <div className="overflow-hidden">
              <h2 className="font-bold text-white text-sm truncate">{business?.name || 'WhatsApp Bot'}</h2>
              <div className="flex items-center gap-1.5 mt-0.5">
                <div className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
                <span className="text-[11px] text-slate-400 font-medium">Online</span>
              </div>
            </div>
          </div>
          {/* Desktop hide button */}
          <button
            onClick={onToggleCollapse}
            title="Hide Sidebar"
            className="hidden md:flex p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            aria-label="Hide Sidebar"
          >
            <IconChevronLeft className="w-4 h-4" />
          </button>
          {/* Mobile close button */}
          <button
            onClick={() => setMobileOpen(false)}
            className="md:hidden p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
          >
            <IconClose className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation items */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                  active
                    ? 'bg-brand-500 text-slate-950 shadow-md shadow-brand-500/15 font-bold'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </div>
                {item.badge > 0 && (
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      active
                        ? 'bg-slate-950 text-brand-400'
                        : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* User profile & logout */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/40">
        <div className="flex items-center justify-between">
          <div className="truncate mr-2">
            <div className="text-xs font-semibold text-white truncate">{user?.email}</div>
            <div className="text-[10px] text-slate-500">Administrator</div>
          </div>
          <button
            onClick={onLogout}
            title="Sign Out"
            className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors"
          >
            <IconLogout className="w-4 h-4" />
          </button>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop Sidebar (Collapsible) */}
      <aside
        className={`hidden md:flex bg-slate-900 border-r border-slate-800 flex-col justify-between shrink-0 select-none transition-all duration-300 ease-in-out overflow-hidden ${
          sidebarCollapsed ? 'w-0 opacity-0 border-none pointer-events-none' : 'w-64 opacity-100'
        }`}
      >
        <div className="w-64 flex flex-col justify-between h-full">
          {sidebarContent}
        </div>
      </aside>

      {/* Mobile Drawer (Overlay + Drawer) */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileOpen(false)}
          />

          {/* Drawer Body */}
          <aside className="relative w-72 max-w-[85vw] bg-slate-900 border-r border-slate-800 flex flex-col justify-between z-10 shadow-2xl">
            {sidebarContent}
          </aside>
        </div>
      )}
    </>
  );
}

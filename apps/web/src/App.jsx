import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import LoginView from './views/LoginView';
import SetupView from './views/SetupView';
import ConversationsView from './views/ConversationsView';
import HandoffView from './views/HandoffView';
import ProductsView from './views/ProductsView';
import OrdersView from './views/OrdersView';
import UsageView from './views/UsageView';
import SettingsView from './views/SettingsView';
import {
  IconMenu,
  IconChat,
  IconInbox,
  IconProduct,
  IconOrder,
  IconSettings,
} from './components/Icons';

export default function App() {
  const [user, setUser] = useState(null);
  const [initialized, setInitialized] = useState(true);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [showSetup, setShowSetup] = useState(false);
  const [activeTab, setActiveTab] = useState('conversations');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Check auth and initial setup status
  const checkAuth = async () => {
    try {
      const meRes = await fetch('/api/auth/me');
      if (meRes.ok) {
        const userData = await meRes.json();
        setUser(userData);
        setCheckingAuth(false);
        return;
      }

      const statusRes = await fetch('/api/auth/status');
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setInitialized(statusData.initialized);
        if (!statusData.initialized) {
          setShowSetup(true);
        }
      }
    } catch {
      // API may be temporarily down or starting up
    } finally {
      setCheckingAuth(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } finally {
      setUser(null);
    }
  };

  if (checkingAuth) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-400 text-sm">Connecting to WhatsApp Bot...</span>
        </div>
      </div>
    );
  }

  // Not logged in: show Setup or Login
  if (!user) {
    if (showSetup || !initialized) {
      return (
        <SetupView
          onSetupSuccess={(userData) => {
            setUser(userData);
            setInitialized(true);
            setShowSetup(false);
          }}
          onBackToLogin={() => setShowSetup(false)}
        />
      );
    }
    return (
      <LoginView
        onLoginSuccess={(userData) => setUser(userData)}
        onGoToSetup={() => setShowSetup(true)}
      />
    );
  }

  const mobileNavTabs = [
    { id: 'conversations', label: 'Chats', icon: IconChat },
    { id: 'handoff', label: 'Inbox', icon: IconInbox },
    { id: 'products', label: 'Products', icon: IconProduct },
    { id: 'orders', label: 'Orders', icon: IconOrder },
    { id: 'settings', label: 'Settings', icon: IconSettings },
  ];

  // Logged in: Main Dashboard
  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans overflow-hidden">
      {/* Responsive Sidebar (Desktop fixed + Mobile slide drawer) */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        business={{ id: user.business_id, name: user.business_name }}
        user={user}
        onLogout={handleLogout}
        mobileOpen={mobileSidebarOpen}
        setMobileOpen={setMobileSidebarOpen}
      />

      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Mobile Top Header */}
        <header className="md:hidden flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileSidebarOpen(true)}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
              aria-label="Open Navigation"
            >
              <IconMenu className="w-6 h-6" />
            </button>
            <div className="font-bold text-sm text-white truncate max-w-[180px]">
              {user.business_name || 'WhatsApp Bot'}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
            <span className="text-xs text-slate-400 capitalize">{activeTab}</span>
          </div>
        </header>

        {/* Main Content Area (padded bottom on mobile for bottom nav) */}
        <main className="flex-1 flex overflow-hidden pb-14 md:pb-0">
          {activeTab === 'conversations' && (
            <ConversationsView businessId={user.business_id} />
          )}
          {activeTab === 'handoff' && (
            <HandoffView
              businessId={user.business_id}
              onSelectConversation={() => setActiveTab('conversations')}
            />
          )}
          {activeTab === 'products' && (
            <ProductsView businessId={user.business_id} />
          )}
          {activeTab === 'orders' && (
            <OrdersView businessId={user.business_id} />
          )}
          {activeTab === 'usage' && (
            <UsageView businessId={user.business_id} />
          )}
          {activeTab === 'settings' && (
            <SettingsView businessId={user.business_id} />
          )}
        </main>

        {/* Mobile Bottom Navigation Bar */}
        <nav className="md:hidden fixed bottom-0 left-0 right-0 h-14 bg-slate-900/95 backdrop-blur border-t border-slate-800 flex items-center justify-around px-2 z-40">
          {mobileNavTabs.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex flex-col items-center justify-center flex-1 py-1 transition-colors ${
                  active ? 'text-brand-400 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="w-5 h-5 mb-0.5" />
                <span className="text-[10px] tracking-tight">{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </div>
  );
}

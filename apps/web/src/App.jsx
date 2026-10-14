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

export default function App() {
  const [user, setUser] = useState(null);
  const [initialized, setInitialized] = useState(true);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [showSetup, setShowSetup] = useState(false);
  const [activeTab, setActiveTab] = useState('conversations');

  // Check auth and initial setup status
  const checkAuth = async () => {
    try {
      // 1. Try to fetch current user
      const meRes = await fetch('/api/auth/me');
      if (meRes.ok) {
        const userData = await meRes.json();
        setUser(userData);
        setCheckingAuth(false);
        return;
      }

      // 2. If not authenticated, check system setup status
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

  // Logged in: Main Dashboard
  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans overflow-hidden">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        business={{ id: user.business_id, name: user.business_name }}
        user={user}
        onLogout={handleLogout}
      />

      <main className="flex-1 flex overflow-hidden">
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
    </div>
  );
}

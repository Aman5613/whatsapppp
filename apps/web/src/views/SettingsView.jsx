import React, { useState, useEffect } from 'react';
import { IconCopy, IconCheck, IconDatabase } from '../components/Icons';

export default function SettingsView({ businessId }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [copiedWebhook, setCopiedWebhook] = useState(false);
  const [copiedToken, setCopiedToken] = useState(false);

  // Form fields
  const [businessName, setBusinessName] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [languagePref, setLanguagePref] = useState('hinglish');
  const [tone, setTone] = useState('friendly and professional');
  const [aiProvider, setAiProvider] = useState('openai');
  const [aiModel, setAiModel] = useState('gpt-4o-mini');
  const [aiKey, setAiKey] = useState('');
  const [fallbackProvider, setFallbackProvider] = useState('');
  const [fallbackModel, setFallbackModel] = useState('');
  const [fallbackKey, setFallbackKey] = useState('');

  // WhatsApp fields
  const [phoneId, setPhoneId] = useState('');
  const [wabaId, setWabaId] = useState('');
  const [waToken, setWaToken] = useState('');
  const [waSecret, setWaSecret] = useState('');
  const [waVerifyToken, setWaVerifyToken] = useState('');

  // Test states
  const [testingAi, setTestingAi] = useState(false);
  const [aiTestResult, setAiTestResult] = useState(null);
  const [testingWa, setTestingWa] = useState(false);
  const [waTestResult, setWaTestResult] = useState(null);

  // Database Connection Wizard
  const [dbStatus, setDbStatus] = useState(null);
  const [newDbUrl, setNewDbUrl] = useState('');
  const [testingDb, setTestingDb] = useState(false);
  const [dbTestResult, setDbTestResult] = useState(null);
  const [applyingDb, setApplyingDb] = useState(false);
  const [dbApplyResult, setDbApplyResult] = useState(null);

  const fetchSettings = async () => {
    try {
      const res = await fetch(`/api/settings?business_id=${businessId}`);
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        setBusinessName(data.business_name || '');
        setSystemPrompt(data.system_prompt || '');
        setLanguagePref(data.language_pref || 'hinglish');
        setTone(data.tone || 'friendly and professional');
        setAiProvider(data.ai_provider || 'openai');
        setAiModel(data.ai_model || 'gpt-4o-mini');
        setFallbackProvider(data.fallback_provider || '');
        setFallbackModel(data.fallback_model || '');

        if (data.whatsapp) {
          setPhoneId(data.whatsapp.phone_number_id || '');
          setWabaId(data.whatsapp.waba_id || '');
          setWaVerifyToken(data.whatsapp.verify_token || '');
        }
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchDbStatus = async () => {
    try {
      const res = await fetch('/api/settings/database/status');
      if (res.ok) {
        setDbStatus(await res.json());
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchSettings();
    fetchDbStatus();
  }, [businessId]);

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSaving(true);
    setNotice('');

    const body = {
      business_name: businessName,
      system_prompt: systemPrompt,
      language_pref: languagePref,
      tone,
      ai_provider: aiProvider,
      ai_model: aiModel,
      whatsapp_phone_number_id: phoneId,
      whatsapp_waba_id: wabaId,
      whatsapp_verify_token: waVerifyToken,
    };

    if (aiKey.trim()) body.ai_api_key = aiKey.trim();
    if (fallbackProvider) body.fallback_provider = fallbackProvider;
    if (fallbackModel) body.fallback_model = fallbackModel;
    if (fallbackKey.trim()) body.fallback_key = fallbackKey.trim();
    if (waToken.trim()) body.whatsapp_access_token = waToken.trim();
    if (waSecret.trim()) body.whatsapp_app_secret = waSecret.trim();

    try {
      const res = await fetch(`/api/settings?business_id=${businessId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setNotice('Settings and credentials saved securely.');
        setAiKey('');
        setFallbackKey('');
        setWaToken('');
        setWaSecret('');
        await fetchSettings();
      }
    } finally {
      setSaving(false);
    }
  };

  const handleTestAi = async () => {
    setTestingAi(true);
    setAiTestResult(null);
    try {
      const res = await fetch(`/api/settings/test-ai?business_id=${businessId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: aiProvider,
          model: aiModel,
          api_key: aiKey.trim() || undefined,
        }),
      });
      const data = await res.json();
      setAiTestResult(data);
    } finally {
      setTestingAi(false);
    }
  };

  const handleTestWhatsApp = async () => {
    setTestingWa(true);
    setWaTestResult(null);
    try {
      const res = await fetch(`/api/settings/test-whatsapp?business_id=${businessId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone_number_id: phoneId,
          access_token: waToken.trim() || undefined,
        }),
      });
      const data = await res.json();
      setWaTestResult(data);
    } finally {
      setTestingWa(false);
    }
  };

  const handleTestDb = async () => {
    if (!newDbUrl.trim()) return;
    setTestingDb(true);
    setDbTestResult(null);
    try {
      const res = await fetch('/api/settings/database/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ database_url: newDbUrl.trim() }),
      });
      const data = await res.json();
      setDbTestResult(data);
    } finally {
      setTestingDb(false);
    }
  };

  const handleApplyDb = async () => {
    if (!newDbUrl.trim()) return;
    setApplyingDb(true);
    setDbApplyResult(null);
    try {
      const res = await fetch('/api/settings/database/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ database_url: newDbUrl.trim() }),
      });
      const data = await res.json();
      setDbApplyResult(data);
      if (res.ok) {
        setNewDbUrl('');
        await fetchDbStatus();
      }
    } finally {
      setApplyingDb(false);
    }
  };

  const copyToClipboard = (text, setCopied) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-16 text-slate-500">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const dynamicWebhookUrl = settings?.webhook_key
    ? `${window.location.origin}/webhook/${settings.webhook_key}`
    : (settings?.webhook_url || '');

  return (
    <div className="flex-1 flex flex-col p-8 overflow-y-auto bg-slate-950 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">System & Business Settings</h1>
        <p className="text-slate-400 text-sm mt-1">
          Configure Meta WhatsApp credentials, AI keys, system prompts, and database connection
        </p>
      </div>

      {notice && (
        <div className="p-3 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400 text-sm">
          {notice}
        </div>
      )}

      {/* Webhook Card */}
      <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 shadow-xl">
        <h3 className="text-base font-bold text-white mb-2">Meta Webhook Configuration</h3>
        <p className="text-xs text-slate-400 mb-4">
          Copy this Callback URL into your Meta App Dashboard under WhatsApp &gt; Configuration &gt; Webhook
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Callback URL
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                readOnly
                value={dynamicWebhookUrl}
                className="flex-1 px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs font-mono text-slate-200"
              />
              <button
                type="button"
                onClick={() => copyToClipboard(dynamicWebhookUrl, setCopiedWebhook)}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs flex items-center gap-1"
              >
                {copiedWebhook ? <IconCheck className="w-4 h-4 text-brand-400" /> : <IconCopy className="w-4 h-4" />}
                <span>{copiedWebhook ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Verify Token
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                readOnly
                value={settings?.whatsapp?.verify_token || ''}
                className="flex-1 px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs font-mono text-slate-200"
              />
              <button
                type="button"
                onClick={() => copyToClipboard(settings?.whatsapp?.verify_token, setCopiedToken)}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs flex items-center gap-1"
              >
                {copiedToken ? <IconCheck className="w-4 h-4 text-brand-400" /> : <IconCopy className="w-4 h-4" />}
                <span>{copiedToken ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <form onSubmit={handleSaveSettings} className="space-y-8">
        {/* WhatsApp Meta Credentials */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-white">Meta WhatsApp Cloud API</h3>
              <p className="text-xs text-slate-400 mt-0.5">Credentials from Meta for Developers portal</p>
            </div>
            <button
              type="button"
              onClick={handleTestWhatsApp}
              disabled={testingWa}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700"
            >
              {testingWa ? 'Testing Graph API...' : 'Test WhatsApp Connection'}
            </button>
          </div>

          {waTestResult && (
            <div
              className={`mb-4 p-3 rounded-xl border text-xs ${
                waTestResult.success
                  ? 'bg-brand-500/10 border-brand-500/20 text-brand-400'
                  : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
              }`}
            >
              {waTestResult.message}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">
                Phone Number ID
              </label>
              <input
                type="text"
                value={phoneId}
                onChange={(e) => setPhoneId(e.target.value)}
                placeholder="e.g. 104928374829102"
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">
                WABA ID (WhatsApp Business Account ID)
              </label>
              <input
                type="text"
                value={wabaId}
                onChange={(e) => setWabaId(e.target.value)}
                placeholder="e.g. 192837465019283"
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">
                Access Token {settings?.whatsapp?.has_access_token && `(Current: ${settings.whatsapp.access_token_masked})`}
              </label>
              <input
                type="password"
                value={waToken}
                onChange={(e) => setWaToken(e.target.value)}
                placeholder="Enter new Meta access token to update..."
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">
                App Secret {settings?.whatsapp?.has_app_secret && `(Current: ${settings.whatsapp.app_secret_masked})`}
              </label>
              <input
                type="password"
                value={waSecret}
                onChange={(e) => setWaSecret(e.target.value)}
                placeholder="Enter new Meta app secret to update..."
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>
        </div>

        {/* AI Provider Settings */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-white">AI Provider Configuration</h3>
              <p className="text-xs text-slate-400 mt-0.5">Primary model and fallback provider settings</p>
            </div>
            <button
              type="button"
              onClick={handleTestAi}
              disabled={testingAi}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700"
            >
              {testingAi ? 'Pinging Model...' : 'Test Primary AI Model'}
            </button>
          </div>

          {aiTestResult && (
            <div
              className={`mb-4 p-3 rounded-xl border text-xs ${
                aiTestResult.success
                  ? 'bg-brand-500/10 border-brand-500/20 text-brand-400'
                  : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
              }`}
            >
              {aiTestResult.message} {aiTestResult.latency_ms > 0 && `(${aiTestResult.latency_ms}ms)`}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Primary Provider</label>
              <select
                value={aiProvider}
                onChange={(e) => setAiProvider(e.target.value)}
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="gemini">Google Gemini</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Primary Model</label>
              <input
                type="text"
                value={aiModel}
                onChange={(e) => setAiModel(e.target.value)}
                placeholder="gpt-4o-mini, claude-3-5-sonnet, gemini-1.5-flash"
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">
                API Key {settings?.has_ai_key && `(Current: ${settings.ai_key_masked})`}
              </label>
              <input
                type="password"
                value={aiKey}
                onChange={(e) => setAiKey(e.target.value)}
                placeholder="Enter new key to update..."
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-slate-800/60 mb-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Fallback Provider (Optional)</label>
              <select
                value={fallbackProvider}
                onChange={(e) => setFallbackProvider(e.target.value)}
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500"
              >
                <option value="">None (No Fallback)</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="gemini">Google Gemini</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Fallback Model</label>
              <input
                type="text"
                value={fallbackModel}
                onChange={(e) => setFallbackModel(e.target.value)}
                placeholder="e.g. gemini-1.5-flash"
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">
                Fallback API Key {settings?.has_fallback_key && `(Current: ${settings.fallback_key_masked})`}
              </label>
              <input
                type="password"
                value={fallbackKey}
                onChange={(e) => setFallbackKey(e.target.value)}
                placeholder="Enter fallback key..."
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">System Prompt</label>
            <textarea
              rows={4}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-brand-500 resize-none font-sans"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-slate-950 font-bold rounded-xl transition-all shadow-lg shadow-brand-500/20"
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </form>

      {/* Database Connection Wizard */}
      <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
              <IconDatabase className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Database Connection Manager</h3>
              <p className="text-xs text-slate-400">
                Connect and dynamically migrate your Neon PostgreSQL / Supabase database without restarting
              </p>
            </div>
          </div>
          <span
            className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase ${
              dbStatus?.connected
                ? 'bg-brand-500/10 text-brand-400 border border-brand-500/20'
                : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
            }`}
          >
            {dbStatus?.connected ? `Connected (${dbStatus.is_sqlite ? 'SQLite' : 'PostgreSQL'})` : 'Disconnected'}
          </span>
        </div>

        {dbTestResult && (
          <div
            className={`mb-4 p-3 rounded-xl border text-xs ${
              dbTestResult.success
                ? 'bg-brand-500/10 border-brand-500/20 text-brand-400'
                : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
            }`}
          >
            {dbTestResult.message}
          </div>
        )}

        {dbApplyResult && (
          <div
            className={`mb-4 p-3 rounded-xl border text-xs ${
              dbApplyResult.success
                ? 'bg-brand-500/10 border-brand-500/20 text-brand-400'
                : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
            }`}
          >
            {dbApplyResult.message}
          </div>
        )}

        <div className="space-y-3">
          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
            New Database Connection String (Neon / Supabase PostgreSQL)
          </label>
          <input
            type="password"
            value={newDbUrl}
            onChange={(e) => setNewDbUrl(e.target.value)}
            placeholder="postgresql://user:password@ep-xyz.neon.tech/neondb?sslmode=require"
            className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-sm font-mono text-white focus:outline-none focus:border-brand-500"
          />

          <div className="flex gap-2 justify-end pt-2">
            <button
              type="button"
              onClick={handleTestDb}
              disabled={!newDbUrl.trim() || testingDb}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 disabled:opacity-50"
            >
              {testingDb ? 'Testing Connection...' : '1. Test Connection'}
            </button>
            <button
              type="button"
              onClick={handleApplyDb}
              disabled={!newDbUrl.trim() || applyingDb}
              className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-slate-950 text-xs font-bold rounded-xl disabled:opacity-50 shadow-md shadow-brand-500/10"
            >
              {applyingDb ? 'Migrating & Rebinding...' : '2. Apply & Run Migrations'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

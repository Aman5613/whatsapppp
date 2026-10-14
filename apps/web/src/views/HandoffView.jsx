import React, { useState, useEffect } from 'react';
import { IconUser, IconChat } from '../components/Icons';

export default function HandoffView({ businessId, onSelectConversation }) {
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoReturning, setAutoReturning] = useState(false);
  const [notice, setNotice] = useState('');

  const fetchQueue = async () => {
    try {
      const res = await fetch(`/api/handoff?business_id=${businessId}`);
      if (res.ok) {
        const data = await res.json();
        setQueue(data);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
    const interval = setInterval(fetchQueue, 4000);
    return () => clearInterval(interval);
  }, [businessId]);

  const handleTriggerAutoReturn = async () => {
    setAutoReturning(true);
    setNotice('');
    try {
      const res = await fetch(`/api/handoff/auto-return?business_id=${businessId}&timeout_minutes=60`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setNotice(`Auto-returned ${data.returned_count} inactive conversation(s) to bot.`);
        await fetchQueue();
      }
    } finally {
      setAutoReturning(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-8 overflow-y-auto bg-slate-950">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
            Handoff Inbox
            {queue.length > 0 && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                {queue.length} pending
              </span>
            )}
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Conversations that have requested human assistance or are currently assigned to operators
          </p>
        </div>

        <button
          onClick={handleTriggerAutoReturn}
          disabled={autoReturning}
          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-semibold rounded-xl border border-slate-750 transition-colors"
        >
          {autoReturning ? 'Processing...' : 'Run Auto-Return (60m+ idle)'}
        </button>
      </div>

      {notice && (
        <div className="mb-6 p-3 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400 text-sm">
          {notice}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center p-16 text-slate-500">
          <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : queue.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-16 border border-dashed border-slate-800/80 rounded-2xl bg-slate-900/20">
          <div className="w-12 h-12 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400 mb-3">
            <IconUser className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-white">Inbox Clean</h3>
          <p className="text-sm text-slate-400 mt-1">All conversations are being handled automatically by the AI.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {queue.map((item) => (
            <div
              key={item.conversation_id}
              className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-5 hover:border-slate-700 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-white text-base">
                    {item.customer_name || item.customer_phone}
                  </span>
                  <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    Needs Action
                  </span>
                </div>

                <div className="text-xs text-slate-400 mb-3">{item.customer_phone}</div>

                <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800/60 mb-4">
                  <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Last Message ({item.last_message_role || 'user'})
                  </div>
                  <div className="text-xs text-slate-200 line-clamp-3">
                    {item.last_message_body || 'No messages'}
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between">
                <span className="text-[11px] text-slate-500">
                  Waiting since {new Date(item.last_customer_message_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                <button
                  onClick={() => onSelectConversation(item.conversation_id)}
                  className="px-3.5 py-1.5 bg-brand-500 hover:bg-brand-600 text-slate-950 font-semibold text-xs rounded-xl transition-all shadow-md shadow-brand-500/10 flex items-center gap-1.5"
                >
                  <IconChat className="w-3.5 h-3.5" />
                  Take Over
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

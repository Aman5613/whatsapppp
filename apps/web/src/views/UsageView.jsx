import React, { useState, useEffect } from 'react';

export default function UsageView({ businessId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchUsage = async () => {
    try {
      const res = await fetch(`/api/usage?business_id=${businessId}`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsage();
    const interval = setInterval(fetchUsage, 10000);
    return () => clearInterval(interval);
  }, [businessId]);

  return (
    <div className="flex-1 flex flex-col p-8 overflow-y-auto bg-slate-950">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white tracking-tight">Token Usage & Cost Analytics</h1>
        <p className="text-slate-400 text-sm mt-1">
          Monitor LLM token consumption, latency, and operational expense across all conversations
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-16 text-slate-500">
          <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : !data ? (
        <div className="p-8 text-center text-slate-500 text-sm">Failed to load analytics data</div>
      ) : (
        <div className="space-y-8">
          {/* Top KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-5 bg-slate-900/70 border border-slate-800/80 rounded-2xl">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Total Conversations
              </span>
              <div className="text-3xl font-extrabold text-white mt-2">
                {data.total_conversations}
              </div>
              <span className="text-[11px] text-slate-500 mt-1 block">Active & past threads</span>
            </div>

            <div className="p-5 bg-slate-900/70 border border-slate-800/80 rounded-2xl">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Total Messages
              </span>
              <div className="text-3xl font-extrabold text-white mt-2">
                {data.total_messages}
              </div>
              <span className="text-[11px] text-slate-500 mt-1 block">Inbound & outbound</span>
            </div>

            <div className="p-5 bg-slate-900/70 border border-slate-800/80 rounded-2xl">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Total AI Tokens
              </span>
              <div className="text-3xl font-extrabold text-brand-400 mt-2">
                {data.total_tokens.toLocaleString()}
              </div>
              <span className="text-[11px] text-slate-500 mt-1 block">
                {data.total_input_tokens.toLocaleString()} in / {data.total_output_tokens.toLocaleString()} out
              </span>
            </div>

            <div className="p-5 bg-slate-900/70 border border-slate-800/80 rounded-2xl">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Estimated Cost
              </span>
              <div className="text-3xl font-extrabold text-white mt-2">
                ${data.total_estimated_cost.toFixed(4)}
              </div>
              <span className="text-[11px] text-slate-500 mt-1 block">Based on provider rates</span>
            </div>
          </div>

          {/* Breakdown by Provider / Model */}
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 shadow-xl">
            <h3 className="text-base font-bold text-white mb-4">Model Consumption Breakdown</h3>
            {data.breakdown_by_model.length === 0 ? (
              <div className="text-sm text-slate-500">No AI calls recorded yet.</div>
            ) : (
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-950/80 text-xs uppercase font-semibold text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Provider</th>
                    <th className="px-4 py-3">Model</th>
                    <th className="px-4 py-3">Total Calls</th>
                    <th className="px-4 py-3">Input Tokens</th>
                    <th className="px-4 py-3">Output Tokens</th>
                    <th className="px-4 py-3">Est. Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {data.breakdown_by_model.map((row, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 uppercase font-bold text-xs text-white">
                        {row.provider}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-brand-400">
                        {row.model}
                      </td>
                      <td className="px-4 py-3">{row.calls}</td>
                      <td className="px-4 py-3">{row.input_tokens.toLocaleString()}</td>
                      <td className="px-4 py-3">{row.output_tokens.toLocaleString()}</td>
                      <td className="px-4 py-3 font-semibold text-white">
                        ${row.estimated_cost.toFixed(5)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Recent Invocations Log */}
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 shadow-xl">
            <h3 className="text-base font-bold text-white mb-4">Recent Invocations Log</h3>
            {data.recent_logs.length === 0 ? (
              <div className="text-sm text-slate-500">No invocation logs found.</div>
            ) : (
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-950/80 text-xs uppercase font-semibold text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Model</th>
                    <th className="px-4 py-3">Tokens</th>
                    <th className="px-4 py-3">Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                  {data.recent_logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 text-slate-400">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-white">
                        {log.provider}/{log.model}
                      </td>
                      <td className="px-4 py-3 text-brand-400">
                        {log.total_tokens} ({log.input_tokens} in / {log.output_tokens} out)
                      </td>
                      <td className="px-4 py-3 text-slate-300">
                        {log.latency_ms} ms
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

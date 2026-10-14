import React, { useState, useEffect } from 'react';
import { IconOrder, IconUpload } from '../components/Icons';

export default function OrdersView({ businessId }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showImportModal, setShowImportModal] = useState(false);

  // CSV Import state
  const [csvFile, setCsvFile] = useState(null);
  const [dryRunReport, setDryRunReport] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importNotice, setImportNotice] = useState('');

  const fetchOrders = async () => {
    try {
      const res = await fetch(`/api/orders?business_id=${businessId}&limit=100`);
      if (res.ok) {
        const data = await res.json();
        setOrders(data);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [businessId]);

  const handleRunDryRun = async () => {
    if (!csvFile) return;
    setImporting(true);
    setDryRunReport(null);
    setImportNotice('');

    const formData = new FormData();
    formData.append('file', csvFile);

    try {
      const res = await fetch(`/api/orders/import?business_id=${businessId}&dry_run=true`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      setDryRunReport(data);
    } finally {
      setImporting(false);
    }
  };

  const handleCommitImport = async () => {
    if (!csvFile) return;
    setImporting(true);

    const formData = new FormData();
    formData.append('file', csvFile);

    try {
      const res = await fetch(`/api/orders/import?business_id=${businessId}&dry_run=false`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      setImportNotice(`Successfully imported ${data.valid_rows} orders!`);
      setDryRunReport(null);
      setCsvFile(null);
      await fetchOrders();
    } finally {
      setImporting(false);
    }
  };

  const filtered = orders.filter((o) => {
    const q = search.toLowerCase();
    return o.customer_phone?.toLowerCase().includes(q) || o.status?.toLowerCase().includes(q);
  });

  const getStatusBadge = (status) => {
    switch (status?.toLowerCase()) {
      case 'delivered':
        return 'bg-brand-500/10 text-brand-400 border-brand-500/20';
      case 'pending':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'shipped':
        return 'bg-sky-500/10 text-sky-400 border-sky-500/20';
      case 'cancelled':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="flex-1 flex flex-col p-4 sm:p-6 md:p-8 overflow-y-auto bg-slate-950">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Customer Orders</h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Orders placed or tracked by customers via WhatsApp conversations and tools
          </p>
        </div>

        <button
          onClick={() => setShowImportModal(true)}
          className="w-full sm:w-auto px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 transition-colors flex items-center justify-center gap-1.5 shrink-0"
        >
          <IconUpload className="w-4 h-4" />
          Import Orders CSV
        </button>
      </div>

      <div className="mb-4">
        <input
          type="text"
          placeholder="Filter orders by customer phone or status..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-sm px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
        />
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-16 text-slate-500">
          <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : orders.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-16 border border-dashed border-slate-800/80 rounded-2xl bg-slate-900/20">
          <div className="w-12 h-12 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400 mb-3">
            <IconOrder className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-white">No Orders Found</h3>
          <p className="text-sm text-slate-400 mt-1">Orders will appear here as customers place them.</p>
        </div>
      ) : (
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300 min-w-[550px]">
              <thead className="bg-slate-950/80 text-xs uppercase font-semibold text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-6 py-4">Order ID</th>
                  <th className="px-6 py-4">Customer Phone</th>
                  <th className="px-6 py-4">Items Breakdown</th>
                  <th className="px-6 py-4">Total</th>
                  <th className="px-6 py-4">Status</th>
                </tr>
              </thead>

            <tbody className="divide-y divide-slate-800/60">
              {filtered.map((o) => (
                <tr key={o.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-6 py-4 font-mono text-xs text-slate-400">
                    {o.id.slice(0, 8)}...
                  </td>
                  <td className="px-6 py-4 font-semibold text-white">
                    {o.customer_phone}
                  </td>
                  <td className="px-6 py-4">
                    <div className="space-y-1">
                      {o.items?.map((it, idx) => (
                        <div key={idx} className="text-xs text-slate-300 flex items-center gap-1.5">
                          <span className="font-semibold text-white">{it.quantity}x</span>
                          <span>{it.product_name}</span>
                          <span className="text-slate-500">(@ ₹{it.unit_price})</span>
                        </div>
                      ))}
                    </div>
                  </td>
                  <td className="px-6 py-4 font-bold text-white">
                    ₹{o.total?.toFixed(2)}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase border ${getStatusBadge(
                        o.status
                      )}`}
                    >
                      {o.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}


      {/* CSV Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-2">Import Orders from CSV</h3>
            <p className="text-xs text-slate-400 mb-4">
              Columns: <code className="text-brand-400">customer_phone, product_name, quantity, unit_price, status (optional)</code>
            </p>

            {importNotice && (
              <div className="mb-4 p-3 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs">
                {importNotice}
              </div>
            )}

            <div className="border-2 border-dashed border-slate-800 rounded-xl p-6 text-center mb-4 bg-slate-950/40">
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setCsvFile(e.target.files[0])}
                className="block w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700 cursor-pointer"
              />
            </div>

            {dryRunReport && (
              <div className="mb-4 p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs">
                <div className="font-semibold text-white mb-2 flex items-center justify-between">
                  <span>Dry-Run Validation Report</span>
                  <span className={dryRunReport.error_count === 0 ? 'text-brand-400' : 'text-amber-400'}>
                    {dryRunReport.valid_rows} valid / {dryRunReport.total_rows} total
                  </span>
                </div>
                {dryRunReport.errors.length > 0 && (
                  <div className="max-h-32 overflow-y-auto space-y-1 mt-2 text-rose-400">
                    {dryRunReport.errors.map((err, idx) => (
                      <div key={idx}>• Row {err.row}: {err.error}</div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => {
                  setShowImportModal(false);
                  setDryRunReport(null);
                  setCsvFile(null);
                }}
                className="px-4 py-2 bg-slate-800 text-slate-300 text-xs font-semibold rounded-xl hover:bg-slate-700"
              >
                Close
              </button>
              <button
                type="button"
                onClick={handleRunDryRun}
                disabled={!csvFile || importing}
                className="px-4 py-2 bg-slate-700 text-white text-xs font-semibold rounded-xl hover:bg-slate-600 disabled:opacity-50"
              >
                {importing ? 'Validating...' : '1. Test Dry Run'}
              </button>
              <button
                type="button"
                onClick={handleCommitImport}
                disabled={!csvFile || importing || !dryRunReport}
                className="px-4 py-2 bg-brand-500 text-slate-950 text-xs font-semibold rounded-xl hover:bg-brand-600 disabled:opacity-50 shadow-md shadow-brand-500/10"
              >
                2. Confirm Import
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

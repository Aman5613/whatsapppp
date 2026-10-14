import React, { useState, useEffect } from 'react';
import { IconProduct, IconUpload } from '../components/Icons';

export default function ProductsView({ businessId }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);

  // New product form
  const [newName, setNewName] = useState('');
  const [newPrice, setNewPrice] = useState('');
  const [newStock, setNewStock] = useState('0');
  const [newCategory, setNewCategory] = useState('');
  const [newDesc, setNewDesc] = useState('');

  // CSV Import state
  const [csvFile, setCsvFile] = useState(null);
  const [dryRunReport, setDryRunReport] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importNotice, setImportNotice] = useState('');

  const fetchProducts = async () => {
    try {
      const res = await fetch(`/api/products?business_id=${businessId}&limit=100`);
      if (res.ok) {
        const data = await res.json();
        setProducts(data);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, [businessId]);

  const handleCreateProduct = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`/api/products?business_id=${businessId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName,
          price: parseFloat(newPrice),
          stock: parseInt(newStock, 10),
          category: newCategory || null,
          description: newDesc || null,
        }),
      });
      if (res.ok) {
        setShowAddModal(false);
        setNewName('');
        setNewPrice('');
        setNewStock('0');
        setNewCategory('');
        setNewDesc('');
        await fetchProducts();
      }
    } catch {
      // ignore
    }
  };

  const handleRunDryRun = async () => {
    if (!csvFile) return;
    setImporting(true);
    setDryRunReport(null);
    setImportNotice('');

    const formData = new FormData();
    formData.append('file', csvFile);

    try {
      const res = await fetch(`/api/products/import?business_id=${businessId}&dry_run=true`, {
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
      const res = await fetch(`/api/products/import?business_id=${businessId}&dry_run=false`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      setImportNotice(`Successfully imported ${data.valid_rows} products!`);
      setDryRunReport(null);
      setCsvFile(null);
      await fetchProducts();
    } finally {
      setImporting(false);
    }
  };

  const filtered = products.filter((p) => {
    const q = search.toLowerCase();
    return p.name.toLowerCase().includes(q) || (p.category && p.category.toLowerCase().includes(q));
  });

  return (
    <div className="flex-1 flex flex-col p-8 overflow-y-auto bg-slate-950">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Products Catalog</h1>
          <p className="text-slate-400 text-sm mt-1">
            Manage your store&apos;s inventory and data queried by AI tools during customer chats
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowImportModal(true)}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 transition-colors flex items-center gap-1.5"
          >
            <IconUpload className="w-4 h-4" />
            Import CSV
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-slate-950 text-xs font-semibold rounded-xl transition-all shadow-lg shadow-brand-500/20"
          >
            + Add Product
          </button>
        </div>
      </div>

      <div className="mb-4">
        <input
          type="text"
          placeholder="Filter products by name or category..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-sm px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
        />
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-16 text-slate-500">
          <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : products.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-16 border border-dashed border-slate-800/80 rounded-2xl bg-slate-900/20">
          <div className="w-12 h-12 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400 mb-3">
            <IconProduct className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-white">No Products Yet</h3>
          <p className="text-sm text-slate-400 mt-1">Add items individually or import in bulk using CSV.</p>
        </div>
      ) : (
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl overflow-hidden shadow-xl">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950/80 text-xs uppercase font-semibold text-slate-400 border-b border-slate-800">
              <tr>
                <th className="px-6 py-4">Name</th>
                <th className="px-6 py-4">Category</th>
                <th className="px-6 py-4">Price</th>
                <th className="px-6 py-4">Stock</th>
                <th className="px-6 py-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.map((p) => (
                <tr key={p.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-6 py-4 font-semibold text-white">
                    <div>{p.name}</div>
                    {p.description && (
                      <div className="text-xs text-slate-500 font-normal line-clamp-1 mt-0.5">
                        {p.description}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700/60">
                      {p.category || 'General'}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-medium text-white">
                    ₹{p.price.toFixed(2)}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                        p.stock > 5
                          ? 'text-brand-400 bg-brand-500/10'
                          : p.stock > 0
                          ? 'text-amber-400 bg-amber-500/10'
                          : 'text-rose-400 bg-rose-500/10'
                      }`}
                    >
                      {p.stock} units
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        p.active
                          ? 'bg-brand-500/10 text-brand-400 border border-brand-500/20'
                          : 'bg-slate-800 text-slate-500'
                      }`}
                    >
                      {p.active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-4">Add New Product</h3>
            <form onSubmit={handleCreateProduct} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Wireless Noise Canceling Headphones"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Price (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                    placeholder="1999.00"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Stock</label>
                  <input
                    type="number"
                    required
                    value={newStock}
                    onChange={(e) => setNewStock(e.target.value)}
                    placeholder="25"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Category</label>
                <input
                  type="text"
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  placeholder="e.g. Audio, Footwear"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Description</label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Product specs, sizing, features..."
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 resize-none"
                />
              </div>
              <div className="pt-3 flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 text-xs font-semibold rounded-xl hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-brand-500 text-slate-950 text-xs font-semibold rounded-xl hover:bg-brand-600 shadow-md shadow-brand-500/10"
                >
                  Save Product
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CSV Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-2">Import Products from CSV</h3>
            <p className="text-xs text-slate-400 mb-4">
              Columns: <code className="text-brand-400">name, price, stock, category, description</code>
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

import React, { useState, useEffect, useRef } from 'react';
import {
  IconSend,
  IconBot,
  IconUser,
  IconBack,
  IconSidebar,
  IconChevronLeft,
  IconChevronRight,
  IconGripVertical,
} from '../components/Icons';
import { useRealtimeEvents } from '../hooks/useRealtimeEvents';

export default function ConversationsView({
  businessId,
  sidebarCollapsed = false,
  onToggleSidebar = () => {},
}) {
  const [conversations, setConversations] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [activeConv, setActiveConv] = useState(null);
  const [filterMode, setFilterMode] = useState('all');
  const [search, setSearch] = useState('');
  const [replyText, setReplyText] = useState('');
  const [sending, setSending] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;

  // Draggable slider width & panel collapse state
  const [chatListWidth, setChatListWidth] = useState(() => {
    const saved = localStorage.getItem('chat_list_width');
    return saved ? Math.max(220, Math.min(650, parseInt(saved, 10))) : 340;
  });
  const [isListCollapsed, setIsListCollapsed] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  // Drag resizer handler for the chat list slider
  const handleSliderMouseDown = (e) => {
    e.preventDefault();
    setIsDragging(true);
    const startX = e.clientX;
    const startWidth = chatListWidth;

    const onMouseMove = (moveEvent) => {
      const delta = moveEvent.clientX - startX;
      const newWidth = Math.max(220, Math.min(650, startWidth + delta));
      setChatListWidth(newWidth);
      localStorage.setItem('chat_list_width', String(newWidth));
    };

    const onMouseUp = () => {
      setIsDragging(false);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };

  // Fetch conversation list
  const fetchConversations = async () => {
    try {
      let url = `/api/conversations?business_id=${businessId}&limit=50`;
      if (filterMode !== 'all') {
        url += `&mode=${filterMode}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
        if (!selectedIdRef.current && data.length > 0 && window.innerWidth >= 768) {
          setSelectedId(data[0].id);
        }
      }
    } catch {
      // ignore network errors
    }
  };

  // Fetch active conversation details
  const fetchActiveConversation = async (id) => {
    if (!id) return;
    try {
      const res = await fetch(`/api/conversations/${id}?business_id=${businessId}`);
      if (res.ok) {
        const data = await res.json();
        setActiveConv(data);
      }
    } catch {
      // ignore
    }
  };

  // Real-time SSE listener
  const handleRealtimeEvent = (type, data) => {
    fetchConversations();
    const currId = selectedIdRef.current;
    if (currId && data?.conversation_id === currId) {
      fetchActiveConversation(currId);
    }
  };

  const { connected } = useRealtimeEvents(businessId, handleRealtimeEvent);

  // Initial load + fallback poll every 60s + window focus
  useEffect(() => {
    fetchConversations();
    const interval = setInterval(fetchConversations, 60000);
    const onFocus = () => fetchConversations();
    window.addEventListener('focus', onFocus);
    return () => {
      clearInterval(interval);
      window.removeEventListener('focus', onFocus);
    };
  }, [businessId, filterMode]);

  useEffect(() => {
    if (selectedId) {
      fetchActiveConversation(selectedId);
    }
  }, [selectedId, businessId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConv?.messages]);

  const handleSendReply = async (e) => {
    e.preventDefault();
    if (!replyText.trim() || !selectedId || sending) return;

    setSending(true);
    setError('');
    try {
      const res = await fetch(`/api/conversations/${selectedId}/messages?business_id=${businessId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body: replyText.trim() }),
      });

      let data = null;
      try {
        data = await res.json();
      } catch {
        // Fallback if response is non-JSON
      }

      if (!res.ok) {
        throw new Error((data && data.detail) || res.statusText || 'Failed to send message');
      }

      setReplyText('');
      await fetchActiveConversation(selectedId);
      await fetchConversations();
    } catch (err) {
      setError(err.message || 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const handleTakeOver = async () => {
    if (!selectedId || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/conversations/${selectedId}/take-over?business_id=${businessId}`, {
        method: 'POST',
      });
      if (res.ok) {
        await fetchActiveConversation(selectedId);
        await fetchConversations();
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleReturnToBot = async () => {
    if (!selectedId || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/conversations/${selectedId}/return-to-bot?business_id=${businessId}`, {
        method: 'POST',
      });
      if (res.ok) {
        await fetchActiveConversation(selectedId);
        await fetchConversations();
      }
    } finally {
      setActionLoading(false);
    }
  };

  // 24 hour window check
  const isWithin24Hours = (timestamp) => {
    if (!timestamp) return false;
    const diff = Date.now() - new Date(timestamp).getTime();
    return diff < 24 * 60 * 60 * 1000;
  };

  const filteredConversations = conversations.filter((c) => {
    const q = search.toLowerCase();
    const phone = c.customer_phone?.toLowerCase() || '';
    const name = c.customer_name?.toLowerCase() || '';
    return phone.includes(q) || name.includes(q);
  });

  return (
    <div className="flex-1 flex overflow-hidden bg-slate-950">
      {/* Sidebar List (Resizable on desktop, collapsible, full width on mobile when no chat is open) */}
      <div
        style={{
          width: isListCollapsed ? '0px' : `${chatListWidth}px`,
        }}
        className={`border-r border-slate-800 flex flex-col bg-slate-900/50 shrink-0 transition-[width] duration-75 overflow-hidden ${
          isListCollapsed ? 'hidden md:flex' : ''
        } ${selectedId ? 'hidden md:flex' : 'w-full flex'}`}
      >
        <div style={{ width: `${chatListWidth}px` }} className="flex flex-col h-full overflow-hidden">
          <div className="p-3 sm:p-4 border-b border-slate-800">
            <div className="flex items-center justify-between mb-2 gap-2">
              <div className="flex items-center gap-1.5">
                {/* Toggle Main App Sidebar Button */}
                <button
                  onClick={onToggleSidebar}
                  title={sidebarCollapsed ? "Show Main Sidebar" : "Hide Main Sidebar"}
                  className="hidden md:flex p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
                  aria-label="Toggle Main Sidebar"
                >
                  <IconSidebar className="w-4 h-4 text-brand-400" />
                </button>
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Chats</span>
              </div>

              <div className="flex items-center gap-1.5">
                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium ${
                  connected ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
                  {connected ? 'Live' : 'Connecting...'}
                </span>

                {/* Collapse Chat List Button */}
                <button
                  onClick={() => setIsListCollapsed(true)}
                  title="Hide Chat List"
                  className="hidden md:flex p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
                  aria-label="Hide Chat List"
                >
                  <IconChevronLeft className="w-4 h-4" />
                </button>
              </div>
            </div>
            <input
              type="text"
              placeholder="Search chats by phone or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
            />
            <div className="flex gap-2 mt-2.5">
              {['all', 'bot', 'human'].map((mode) => (
                <button
                  key={mode}
                  onClick={() => setFilterMode(mode)}
                  className={`flex-1 py-1 px-2.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                    filterMode === mode
                      ? 'bg-brand-500 text-slate-950 font-semibold'
                      : 'bg-slate-800/60 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/40">
            {filteredConversations.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">No conversations found</div>
            ) : (
              filteredConversations.map((conv) => {
                const active = conv.id === selectedId;
                const isHuman = conv.mode === 'human';
                return (
                  <div
                    key={conv.id}
                    onClick={() => setSelectedId(conv.id)}
                    className={`p-3.5 sm:p-4 cursor-pointer transition-colors ${
                      active ? 'bg-slate-800/80 border-l-2 border-brand-500' : 'hover:bg-slate-850/50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-white text-sm truncate mr-2">
                        {conv.customer_name || conv.customer_phone}
                      </span>
                      <span
                        className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full shrink-0 ${
                          isHuman
                            ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                            : 'bg-brand-500/10 text-brand-400 border border-brand-500/20'
                        }`}
                      >
                        {conv.mode}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 truncate">
                      {conv.last_message_body || 'No messages yet'}
                    </div>
                    <div className="flex items-center justify-between mt-2 text-[11px] text-slate-500">
                      <span>{conv.customer_phone}</span>
                      <span>
                        {new Date(conv.last_customer_message_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Draggable Resizer Slider Divider (Desktop) */}
      {!isListCollapsed && (
        <div
          onMouseDown={handleSliderMouseDown}
          onDoubleClick={() => {
            setChatListWidth(340);
            localStorage.setItem('chat_list_width', '340');
          }}
          title="Drag to resize chat list (Double-click to reset)"
          className={`hidden md:flex flex-col justify-center items-center w-1.5 hover:w-2 bg-slate-800/80 hover:bg-brand-500 cursor-col-resize select-none transition-all group relative z-10 shrink-0 ${
            isDragging ? 'bg-brand-500 w-2 ring-2 ring-brand-500/50' : ''
          }`}
        >
          <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900 border border-slate-700 rounded py-2 px-0.5 shadow-xl">
            <IconGripVertical className="w-3 h-3 text-brand-400" />
          </div>
        </div>
      )}

      {/* Chat Thread */}
      {activeConv ? (
        <div
          className={`flex-1 flex flex-col bg-slate-950 overflow-hidden ${
            selectedId ? 'flex' : 'hidden md:flex'
          }`}
        >
          {/* Top Bar */}
          <div className="p-3 sm:p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60 backdrop-blur shrink-0">
            <div className="flex items-center gap-2 overflow-hidden mr-2">
              {/* Mobile Back Button */}
              <button
                onClick={() => setSelectedId(null)}
                className="md:hidden p-1.5 -ml-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 shrink-0"
                aria-label="Back to chat list"
              >
                <IconBack className="w-5 h-5" />
              </button>

              {/* Desktop Expand Chat List Button (if collapsed) */}
              {isListCollapsed && (
                <button
                  onClick={() => setIsListCollapsed(false)}
                  title="Show Chat List"
                  className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg text-xs font-semibold border border-slate-700 shrink-0 transition-colors mr-1"
                >
                  <IconChevronRight className="w-4 h-4 text-brand-400" />
                  <span>Chats</span>
                </button>
              )}

              {/* Desktop Toggle Main Sidebar button if sidebar is collapsed */}
              {sidebarCollapsed && (
                <button
                  onClick={onToggleSidebar}
                  title="Show Main Sidebar"
                  className="hidden md:flex items-center gap-1.5 p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 shrink-0 transition-colors mr-1"
                >
                  <IconSidebar className="w-4 h-4 text-brand-400" />
                </button>
              )}

              <div className="overflow-hidden">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-base sm:text-lg font-bold text-white truncate">
                    {activeConv.customer_name || activeConv.customer_phone}
                  </h2>
                  <span
                    className={`text-[10px] sm:text-xs uppercase font-bold px-2 py-0.5 rounded-full ${
                      activeConv.mode === 'human'
                        ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                        : 'bg-brand-500/10 text-brand-400 border border-brand-500/20'
                    }`}
                  >
                    {activeConv.mode}
                  </span>
                  {activeConv.needs_human && (
                    <span className="text-[10px] sm:text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      Needs Human
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-[11px] sm:text-xs text-slate-400 mt-0.5 truncate">
                  <span className="truncate">{activeConv.customer_phone}</span>
                  <span>•</span>
                  <span
                    className={`truncate ${
                      isWithin24Hours(activeConv.last_customer_message_at)
                        ? 'text-brand-400'
                        : 'text-rose-400'
                    }`}
                  >
                    {isWithin24Hours(activeConv.last_customer_message_at)
                      ? '24h Active'
                      : '24h Expired'}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {activeConv.mode === 'bot' ? (
                <button
                  onClick={handleTakeOver}
                  disabled={actionLoading}
                  className="px-2.5 sm:px-3.5 py-1.5 sm:py-2 bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold rounded-xl transition-all shadow-lg shadow-purple-600/20 flex items-center gap-1.5"
                >
                  <IconUser className="w-4 h-4" />
                  <span className="hidden sm:inline">Take Over</span>
                  <span className="sm:hidden">Takeover</span>
                </button>
              ) : (
                <button
                  onClick={handleReturnToBot}
                  disabled={actionLoading}
                  className="px-2.5 sm:px-3.5 py-1.5 sm:py-2 bg-brand-500 hover:bg-brand-600 text-slate-950 text-xs font-semibold rounded-xl transition-all shadow-lg shadow-brand-500/20 flex items-center gap-1.5"
                >
                  <IconBot className="w-4 h-4" />
                  <span>Return to Bot</span>
                </button>
              )}
            </div>
          </div>

          {/* Messages Stream */}
          <div className="flex-1 overflow-y-auto p-3 sm:p-6 space-y-3 sm:space-y-4">
            {activeConv.messages.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                No messages in this conversation
              </div>
            ) : (
              activeConv.messages.map((m) => {
                const isCustomer = m.role === 'customer';
                const isBot = m.role === 'bot';
                return (
                  <div
                    key={m.id}
                    className={`flex flex-col ${isCustomer ? 'items-start' : 'items-end'}`}
                  >
                    <div
                      className={`max-w-[85%] sm:max-w-md lg:max-w-lg px-3.5 sm:px-4 py-2.5 sm:py-3 rounded-2xl text-xs sm:text-sm leading-relaxed ${
                        isCustomer
                          ? 'bg-slate-900 border border-slate-800 text-slate-100 rounded-tl-sm'
                          : isBot
                          ? 'bg-brand-950/40 border border-brand-500/30 text-brand-100 rounded-tr-sm'
                          : 'bg-purple-950/40 border border-purple-500/30 text-purple-100 rounded-tr-sm'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider mb-1 opacity-70">
                        {isCustomer ? (
                          'Customer'
                        ) : isBot ? (
                          <>
                            <IconBot className="w-3 h-3 text-brand-400" />
                            <span>AI Assistant</span>
                          </>
                        ) : (
                          <>
                            <IconUser className="w-3 h-3 text-purple-400" />
                            <span>Human Operator</span>
                          </>
                        )}
                      </div>
                      <div className="whitespace-pre-wrap break-words">{m.body}</div>
                    </div>
                    <span className="text-[10px] text-slate-500 mt-1 px-1">
                      {new Date(m.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                );
              })
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Reply Box */}
          <div className="p-3 sm:p-4 border-t border-slate-800 bg-slate-900/60 backdrop-blur shrink-0">
            {error && (
              <div className="mb-2 p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
                {error}
              </div>
            )}
            <form onSubmit={handleSendReply} className="flex gap-2">
              <input
                type="text"
                placeholder={
                  isWithin24Hours(activeConv.last_customer_message_at)
                    ? 'Type reply as operator...'
                    : '24h service window expired.'
                }
                disabled={!isWithin24Hours(activeConv.last_customer_message_at) || sending}
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                className="flex-1 px-3 sm:px-4 py-2 sm:py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!replyText.trim() || sending || !isWithin24Hours(activeConv.last_customer_message_at)}
                className="px-3.5 sm:px-5 py-2 sm:py-2.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-slate-950 font-semibold rounded-xl transition-all shadow-lg shadow-brand-500/20 flex items-center gap-1.5 shrink-0"
              >
                {sending ? (
                  <div className="w-4 h-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <IconSend className="w-4 h-4" />
                    <span className="hidden sm:inline text-xs sm:text-sm">Send</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      ) : (
        <div className="hidden md:flex flex-1 flex-col items-center justify-center text-slate-500 text-sm gap-3 p-6 text-center">
          {isListCollapsed && (
            <button
              onClick={() => setIsListCollapsed(false)}
              className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold border border-slate-700 transition-colors shadow-lg"
            >
              <IconChevronRight className="w-4 h-4 text-brand-400" />
              <span>Show Chats</span>
            </button>
          )}
          <span>Select a conversation from the left to view messages</span>
        </div>
      )}
    </div>
  );
}


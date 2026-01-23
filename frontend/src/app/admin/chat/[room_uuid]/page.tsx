'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { adminApi, Message, ChatRoom } from '@/lib/api';
import {
  Shield, Trash2, Pin, PinOff, ExternalLink, AlertTriangle, Ban,
  Search, ChevronLeft, ChevronRight, X, Calendar, User, Hash, Copy, Check
} from 'lucide-react';

const MESSAGES_PER_PAGE = 50;

interface BanModalData {
  username: string;
  visitorId: string | null;
  userId: string | null;
  fingerprint: string | null;
  ipAddress: string | null;
  messageId: string;
}

interface BanIdentifiers {
  account: boolean;
  ip: boolean;
  fingerprint: boolean;
}

export default function AdminChatPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = params.room_uuid as string;

  // URL query params
  const initialMessageId = searchParams.get('message_id');
  const initialUsername = searchParams.get('username');
  const initialPage = parseInt(searchParams.get('page') || '1', 10);

  const [chatRoom, setChatRoom] = useState<ChatRoom | null>(null);
  const [chatUrl, setChatUrl] = useState<string>('');
  const [allMessages, setAllMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Pagination
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [totalMessages, setTotalMessages] = useState(0);

  // Filters
  const [usernameFilter, setUsernameFilter] = useState(initialUsername || '');
  const [messageIdFilter, setMessageIdFilter] = useState(initialMessageId || '');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Ban modal
  const [banModalOpen, setBanModalOpen] = useState(false);
  const [banModalData, setBanModalData] = useState<BanModalData | null>(null);
  const [banType, setBanType] = useState<'chat' | 'site'>('chat');
  const [banIdentifiers, setBanIdentifiers] = useState<BanIdentifiers>({ account: false, ip: false, fingerprint: false });
  const [banReason, setBanReason] = useState('');
  const [banExpires, setBanExpires] = useState('');
  const [banLoading, setBanLoading] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  // Copy to clipboard helper
  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  // Highlighted message (from URL param)
  const [highlightedMessageId, setHighlightedMessageId] = useState<string | null>(initialMessageId);

  // Load chat details and messages
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [detailResponse, messagesResponse] = await Promise.all([
          adminApi.getChatDetail(roomId),
          adminApi.getMessages(roomId, 1000, 0), // Load all for filtering
        ]);

        setChatRoom(detailResponse.chat_room);
        setChatUrl(detailResponse.chat_url);

        // Sort oldest first for chronological review
        const sorted = [...messagesResponse.messages].sort(
          (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
        setAllMessages(sorted);
        setTotalMessages(sorted.length);

        // If message_id in URL, find its page
        if (initialMessageId) {
          const msgIndex = sorted.findIndex(m => m.id === initialMessageId);
          if (msgIndex >= 0) {
            const page = Math.floor(msgIndex / MESSAGES_PER_PAGE) + 1;
            setCurrentPage(page);
          }
        }
      } catch (err: unknown) {
        console.error('Failed to load admin chat data:', err);
        if (err && typeof err === 'object' && 'response' in err) {
          const axiosError = err as { response?: { status?: number } };
          if (axiosError.response?.status === 403) {
            setError('Access denied. You must be a staff member to view this page.');
          } else if (axiosError.response?.status === 404) {
            setError('Chat room not found.');
          } else {
            setError('Failed to load chat data. Please try again.');
          }
        } else {
          setError('Failed to load chat data. Please try again.');
        }
      } finally {
        setLoading(false);
      }
    };

    if (roomId) {
      loadData();
    }
  }, [roomId, initialMessageId]);

  // Filter messages
  const filteredMessages = allMessages.filter(msg => {
    // Username filter
    if (usernameFilter && !msg.username.toLowerCase().includes(usernameFilter.toLowerCase())) {
      return false;
    }
    // Message ID filter
    if (messageIdFilter && !msg.id.toLowerCase().includes(messageIdFilter.toLowerCase())) {
      return false;
    }
    // Date from filter
    if (dateFrom) {
      const msgDate = new Date(msg.created_at);
      const fromDate = new Date(dateFrom);
      if (msgDate < fromDate) return false;
    }
    // Date to filter
    if (dateTo) {
      const msgDate = new Date(msg.created_at);
      const toDate = new Date(dateTo);
      toDate.setHours(23, 59, 59, 999);
      if (msgDate > toDate) return false;
    }
    return true;
  });

  // Paginate
  const totalPages = Math.ceil(filteredMessages.length / MESSAGES_PER_PAGE);
  const paginatedMessages = filteredMessages.slice(
    (currentPage - 1) * MESSAGES_PER_PAGE,
    currentPage * MESSAGES_PER_PAGE
  );

  // Update URL with filters
  const updateUrl = useCallback((page: number, msgId?: string) => {
    const params = new URLSearchParams();
    if (page > 1) params.set('page', page.toString());
    if (usernameFilter) params.set('username', usernameFilter);
    if (msgId) params.set('message_id', msgId);

    const queryString = params.toString();
    const newUrl = queryString
      ? `/admin/chat/${roomId}?${queryString}`
      : `/admin/chat/${roomId}`;

    window.history.replaceState({}, '', newUrl);
  }, [roomId, usernameFilter]);

  // Page change
  const goToPage = (page: number) => {
    setCurrentPage(page);
    setHighlightedMessageId(null);
    updateUrl(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Clear filters
  const clearFilters = () => {
    setUsernameFilter('');
    setMessageIdFilter('');
    setDateFrom('');
    setDateTo('');
    setCurrentPage(1);
    setHighlightedMessageId(null);
    window.history.replaceState({}, '', `/admin/chat/${roomId}`);
  };

  // Jump to message
  const jumpToMessage = (messageId: string) => {
    const msgIndex = filteredMessages.findIndex(m => m.id === messageId);
    if (msgIndex >= 0) {
      const page = Math.floor(msgIndex / MESSAGES_PER_PAGE) + 1;
      setCurrentPage(page);
      setHighlightedMessageId(messageId);
      updateUrl(page, messageId);

      // Scroll to message after render
      setTimeout(() => {
        const element = document.getElementById(`msg-${messageId}`);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 100);
    }
  };

  // Delete a message
  const handleDelete = async (messageId: string) => {
    if (!confirm('Are you sure you want to delete this message?')) return;

    try {
      setActionLoading(messageId);
      await adminApi.deleteMessage(roomId, messageId);
      setAllMessages(prev => prev.map(m =>
        m.id === messageId ? { ...m, is_deleted: true } : m
      ));
    } catch (err) {
      console.error('Failed to delete message:', err);
      alert('Failed to delete message');
    } finally {
      setActionLoading(null);
    }
  };

  // Unpin a message
  const handleUnpin = async (messageId: string) => {
    if (!confirm('Are you sure you want to unpin this message?')) return;

    try {
      setActionLoading(messageId);
      await adminApi.unpinMessage(roomId, messageId);
      setAllMessages(prev => prev.map(m =>
        m.id === messageId ? { ...m, is_pinned: false, sticky_until: null } : m
      ));
    } catch (err) {
      console.error('Failed to unpin message:', err);
      alert('Failed to unpin message');
    } finally {
      setActionLoading(null);
    }
  };

  // Open ban modal
  const openBanModal = (message: Message & { participation?: { user_id: string | null; fingerprint: string | null; ip_address: string | null } }) => {
    const hasAccount = !!(message.participation?.user_id || message.user?.id);
    const hasFingerprint = !!message.participation?.fingerprint;

    setBanModalData({
      username: message.username,
      visitorId: message.user?.id || null,
      userId: message.participation?.user_id || message.user?.id || null,
      fingerprint: message.participation?.fingerprint || null,
      ipAddress: message.participation?.ip_address || null,
      messageId: message.id,
    });
    setBanType('chat');
    // Default: select account if available, otherwise fingerprint
    setBanIdentifiers({
      account: hasAccount,
      ip: false,
      fingerprint: !hasAccount && hasFingerprint,
    });
    setBanReason('');
    setBanExpires('');
    setBanModalOpen(true);
  };

  // Submit ban
  const handleBan = async () => {
    if (!banModalData || !banReason.trim()) {
      alert('Please provide a reason for the ban');
      return;
    }

    // Check at least one identifier is selected
    const hasSelection = banIdentifiers.account || banIdentifiers.ip || banIdentifiers.fingerprint;
    if (!hasSelection) {
      alert('Please select at least one ban method (Account, IP, or Fingerprint)');
      return;
    }

    try {
      setBanLoading(true);
      const selectedMethods: string[] = [];

      if (banType === 'site') {
        // Site-wide ban - can ban by multiple identifiers
        // Create separate bans for each selected identifier
        if (banIdentifiers.account && banModalData.userId) {
          await adminApi.createSiteBan({
            username: banModalData.username,
            user_id: banModalData.userId,
            reason: banReason,
            expires_at: banExpires || undefined,
          });
          selectedMethods.push('account');
        }

        if (banIdentifiers.ip && banModalData.ipAddress) {
          await adminApi.createSiteBan({
            username: banModalData.username,
            ip_address: banModalData.ipAddress,
            reason: banReason,
            expires_at: banExpires || undefined,
          });
          selectedMethods.push('IP');
        }

        if (banIdentifiers.fingerprint && banModalData.fingerprint) {
          await adminApi.createSiteBan({
            username: banModalData.username,
            fingerprint: banModalData.fingerprint,
            reason: banReason,
            expires_at: banExpires || undefined,
          });
          selectedMethods.push('fingerprint');
        }

        alert(`Site ban created for ${banModalData.username} (${selectedMethods.join(', ')})`);
      } else {
        // Chat ban - create ban with username (primary) and optionally fingerprint
        await adminApi.createChatBan(roomId, {
          username: banModalData.username,
          fingerprint: banIdentifiers.fingerprint ? banModalData.fingerprint || undefined : undefined,
          reason: banReason || 'Banned by site admin',
        });
        alert(`Chat ban created for ${banModalData.username}`);
      }

      setBanModalOpen(false);
    } catch (err) {
      console.error('Failed to create ban:', err);
      alert('Failed to create ban');
    } finally {
      setBanLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-900 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400 mx-auto mb-4"></div>
          <p className="text-zinc-400">Loading admin view...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-900 text-white flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-xl font-bold mb-2">Error</h1>
          <p className="text-zinc-400 mb-4">{error}</p>
          <button
            onClick={() => router.back()}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-900 text-white">
      {/* Admin Header */}
      <div className="bg-red-900/50 border-b border-red-700 px-4 py-3 sticky top-0 z-50">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <Shield className="w-6 h-6 text-red-400" />
          <span className="font-bold text-red-400">ADMIN MODE</span>
          <span className="text-zinc-400">|</span>
          <span className="text-zinc-300 truncate">{chatRoom?.name}</span>
          <a
            href={chatUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto flex items-center gap-1 text-cyan-400 hover:text-cyan-300 text-sm"
          >
            <ExternalLink className="w-4 h-4" />
            View Chat
          </a>
        </div>
      </div>

      {/* Chat Info */}
      <div className="max-w-5xl mx-auto px-4 py-4 border-b border-zinc-800">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-zinc-500">Room ID:</span>
            <p className="text-zinc-300 font-mono text-xs break-all">{roomId}</p>
          </div>
          <div>
            <span className="text-zinc-500">Code:</span>
            <p className="text-zinc-300">{chatRoom?.code}</p>
          </div>
          <div>
            <span className="text-zinc-500">Host:</span>
            <p className="text-zinc-300">{chatRoom?.host?.reserved_username || 'Unknown'}</p>
          </div>
          <div>
            <span className="text-zinc-500">Total Messages:</span>
            <p className="text-zinc-300">{totalMessages}</p>
          </div>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="max-w-5xl mx-auto px-4 py-4 border-b border-zinc-800">
        <div className="flex flex-wrap gap-3">
          {/* Username Search */}
          <div className="flex items-center gap-2 bg-zinc-800 rounded-lg px-3 py-2">
            <User className="w-4 h-4 text-zinc-500" />
            <input
              type="text"
              placeholder="Username..."
              value={usernameFilter}
              onChange={(e) => {
                setUsernameFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-transparent border-none outline-none text-sm w-32"
            />
          </div>

          {/* Message ID Search */}
          <div className="flex items-center gap-2 bg-zinc-800 rounded-lg px-3 py-2">
            <Hash className="w-4 h-4 text-zinc-500" />
            <input
              type="text"
              placeholder="Message ID..."
              value={messageIdFilter}
              onChange={(e) => {
                setMessageIdFilter(e.target.value);
                setCurrentPage(1);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && messageIdFilter) {
                  jumpToMessage(messageIdFilter);
                }
              }}
              className="bg-transparent border-none outline-none text-sm w-40 font-mono"
            />
            {messageIdFilter && (
              <button
                onClick={() => jumpToMessage(messageIdFilter)}
                className="text-cyan-400 hover:text-cyan-300"
              >
                <Search className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Date From */}
          <div className="flex items-center gap-2 bg-zinc-800 rounded-lg px-3 py-2">
            <Calendar className="w-4 h-4 text-zinc-500" />
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-transparent border-none outline-none text-sm"
            />
          </div>

          {/* Date To */}
          <div className="flex items-center gap-2 bg-zinc-800 rounded-lg px-3 py-2">
            <span className="text-zinc-500 text-sm">to</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-transparent border-none outline-none text-sm"
            />
          </div>

          {/* Clear Filters */}
          {(usernameFilter || messageIdFilter || dateFrom || dateTo) && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-zinc-400 hover:text-white text-sm"
            >
              <X className="w-4 h-4" />
              Clear
            </button>
          )}
        </div>

        {/* Filter Results */}
        <div className="mt-2 text-sm text-zinc-500">
          Showing {filteredMessages.length} of {totalMessages} messages
          {filteredMessages.length !== totalMessages && ' (filtered)'}
        </div>
      </div>

      {/* Messages List */}
      <div className="max-w-5xl mx-auto px-4 py-4">
        {paginatedMessages.length === 0 ? (
          <p className="text-zinc-500 text-center py-8">No messages match your filters.</p>
        ) : (
          <div className="space-y-2">
            {paginatedMessages.map((message) => (
              <div
                key={message.id}
                id={`msg-${message.id}`}
                className={`p-3 rounded-lg border transition-all ${
                  highlightedMessageId === message.id
                    ? 'ring-2 ring-cyan-400 border-cyan-600 bg-cyan-900/20'
                    : message.is_deleted
                    ? 'bg-zinc-800/50 border-zinc-700 opacity-50'
                    : message.is_pinned
                    ? 'bg-purple-900/30 border-purple-700'
                    : message.is_from_host
                    ? 'bg-amber-900/30 border-amber-700'
                    : 'bg-zinc-800 border-zinc-700'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    {/* Message Header */}
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className={`font-semibold text-sm ${
                        message.is_from_host ? 'text-amber-400' :
                        message.is_pinned ? 'text-purple-400' : 'text-zinc-300'
                      }`}>
                        {message.username}
                      </span>
                      {message.is_from_host && (
                        <span className="text-xs bg-amber-600/30 text-amber-400 px-1.5 py-0.5 rounded">HOST</span>
                      )}
                      {message.is_pinned && (
                        <span className="text-xs bg-purple-600/30 text-purple-400 px-1.5 py-0.5 rounded flex items-center gap-1">
                          <Pin className="w-3 h-3" />
                          ${message.pin_amount_paid}
                        </span>
                      )}
                      {message.is_deleted && (
                        <span className="text-xs bg-red-600/30 text-red-400 px-1.5 py-0.5 rounded">DELETED</span>
                      )}
                      <span className="text-xs text-zinc-500">
                        {new Date(message.created_at).toLocaleString()}
                      </span>
                    </div>

                    {/* Message Content */}
                    <p className={`text-sm ${message.is_deleted ? 'text-zinc-500 italic' : 'text-zinc-200'}`}>
                      {message.is_deleted ? '[Message deleted]' : message.content}
                    </p>

                    {/* Message Metadata */}
                    <div className="mt-1 text-xs text-zinc-500 font-mono">
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(message.id);
                          setHighlightedMessageId(message.id);
                          updateUrl(currentPage, message.id);
                        }}
                        className="hover:text-cyan-400"
                        title="Copy message ID"
                      >
                        {message.id}
                      </button>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  {!message.is_deleted && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => openBanModal(message)}
                        disabled={actionLoading === message.id}
                        className="p-2 text-orange-400 hover:bg-orange-900/50 rounded-lg disabled:opacity-50"
                        title="Ban user"
                      >
                        <Ban className="w-4 h-4" />
                      </button>
                      {message.is_pinned && (
                        <button
                          onClick={() => handleUnpin(message.id)}
                          disabled={actionLoading === message.id}
                          className="p-2 text-purple-400 hover:bg-purple-900/50 rounded-lg disabled:opacity-50"
                          title="Unpin message"
                        >
                          <PinOff className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(message.id)}
                        disabled={actionLoading === message.id}
                        className="p-2 text-red-400 hover:bg-red-900/50 rounded-lg disabled:opacity-50"
                        title="Delete message"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6 py-4">
            <button
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage === 1}
              className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-1">
              {/* First page */}
              {currentPage > 3 && (
                <>
                  <button
                    onClick={() => goToPage(1)}
                    className="px-3 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm"
                  >
                    1
                  </button>
                  {currentPage > 4 && <span className="text-zinc-500">...</span>}
                </>
              )}

              {/* Page numbers around current */}
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter(page => Math.abs(page - currentPage) <= 2)
                .map(page => (
                  <button
                    key={page}
                    onClick={() => goToPage(page)}
                    className={`px-3 py-1 rounded-lg text-sm ${
                      page === currentPage
                        ? 'bg-cyan-600 text-white'
                        : 'bg-zinc-800 hover:bg-zinc-700'
                    }`}
                  >
                    {page}
                  </button>
                ))}

              {/* Last page */}
              {currentPage < totalPages - 2 && (
                <>
                  {currentPage < totalPages - 3 && <span className="text-zinc-500">...</span>}
                  <button
                    onClick={() => goToPage(totalPages)}
                    className="px-3 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm"
                  >
                    {totalPages}
                  </button>
                </>
              )}
            </div>

            <button
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-5 h-5" />
            </button>

            <span className="ml-4 text-sm text-zinc-500">
              Page {currentPage} of {totalPages}
            </span>
          </div>
        )}
      </div>

      {/* Ban Modal */}
      {banModalOpen && banModalData && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-800 rounded-xl max-w-md w-full p-6 overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold flex items-center gap-2">
                <Ban className="w-5 h-5 text-orange-400" />
                Ban User
              </h2>
              <button
                onClick={() => setBanModalOpen(false)}
                className="text-zinc-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {/* User Info */}
              <div className="bg-zinc-700/50 rounded-lg p-3 space-y-2">
                <div>
                  <p className="text-xs text-zinc-500">Username</p>
                  <p className="font-semibold">{banModalData.username}</p>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <p className="text-zinc-500">Account</p>
                    <p className={banModalData.userId ? 'text-green-400' : 'text-zinc-500'}>
                      {banModalData.userId ? 'Registered' : 'Guest'}
                    </p>
                  </div>
                  <div className="min-w-0">
                    <p className="text-zinc-500">IP Address</p>
                    <div className="flex items-center gap-1">
                      <p className="font-mono text-zinc-300 text-[10px] truncate flex-1" title={banModalData.ipAddress || 'Unknown'}>
                        {banModalData.ipAddress || 'Unknown'}
                      </p>
                      {banModalData.ipAddress && (
                        <button
                          onClick={() => copyToClipboard(banModalData.ipAddress!, 'ip')}
                          className="text-zinc-400 hover:text-white p-0.5 flex-shrink-0"
                          title="Copy IP address"
                        >
                          {copiedField === 'ip' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
                {banModalData.fingerprint && (
                  <div className="text-xs">
                    <p className="text-zinc-500">Fingerprint</p>
                    <div className="flex items-center gap-1">
                      <p className="font-mono text-zinc-400 truncate text-[10px] flex-1" title={banModalData.fingerprint}>
                        {banModalData.fingerprint.substring(0, 20)}...
                      </p>
                      <button
                        onClick={() => copyToClipboard(banModalData.fingerprint!, 'fingerprint')}
                        className="text-zinc-400 hover:text-white p-0.5 flex-shrink-0"
                        title="Copy fingerprint"
                      >
                        {copiedField === 'fingerprint' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Ban Scope (Chat vs Site) */}
              <div>
                <label className="text-sm text-zinc-400 block mb-2">Ban Scope</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setBanType('chat')}
                    className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium ${
                      banType === 'chat'
                        ? 'bg-orange-600 text-white'
                        : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'
                    }`}
                  >
                    Chat Ban
                  </button>
                  <button
                    onClick={() => setBanType('site')}
                    className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium ${
                      banType === 'site'
                        ? 'bg-red-600 text-white'
                        : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'
                    }`}
                  >
                    Site Ban
                  </button>
                </div>
                <p className="text-xs text-zinc-500 mt-1">
                  {banType === 'chat'
                    ? 'User will be banned from this chat only'
                    : 'User will be banned from ALL chats site-wide'}
                </p>
              </div>

              {/* Ban Identifier (Account/IP/Fingerprint) - Multi-select */}
              <div>
                <label className="text-sm text-zinc-400 block mb-2">Ban By (select all that apply)</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setBanIdentifiers(prev => ({ ...prev, account: !prev.account }))}
                    disabled={!banModalData.userId}
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium border-2 transition-colors ${
                      banIdentifiers.account
                        ? 'bg-blue-600 border-blue-600 text-white'
                        : 'bg-zinc-700 border-zinc-600 text-zinc-300 hover:border-zinc-500'
                    } disabled:opacity-30 disabled:cursor-not-allowed`}
                  >
                    {banIdentifiers.account ? '✓ ' : ''}Account
                  </button>
                  <button
                    onClick={() => setBanIdentifiers(prev => ({ ...prev, ip: !prev.ip }))}
                    disabled={!banModalData.ipAddress}
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium border-2 transition-colors ${
                      banIdentifiers.ip
                        ? 'bg-blue-600 border-blue-600 text-white'
                        : 'bg-zinc-700 border-zinc-600 text-zinc-300 hover:border-zinc-500'
                    } disabled:opacity-30 disabled:cursor-not-allowed`}
                  >
                    {banIdentifiers.ip ? '✓ ' : ''}IP
                  </button>
                  <button
                    onClick={() => setBanIdentifiers(prev => ({ ...prev, fingerprint: !prev.fingerprint }))}
                    disabled={!banModalData.fingerprint}
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium border-2 transition-colors ${
                      banIdentifiers.fingerprint
                        ? 'bg-blue-600 border-blue-600 text-white'
                        : 'bg-zinc-700 border-zinc-600 text-zinc-300 hover:border-zinc-500'
                    } disabled:opacity-30 disabled:cursor-not-allowed`}
                  >
                    {banIdentifiers.fingerprint ? '✓ ' : ''}Fingerprint
                  </button>
                </div>
                <p className="text-xs text-zinc-500 mt-1">
                  Select multiple for stronger enforcement. Account is most reliable, IP may affect shared networks, fingerprint can be evaded.
                </p>
              </div>

              {/* Reason */}
              <div>
                <label className="text-sm text-zinc-400 block mb-2">Reason *</label>
                <textarea
                  value={banReason}
                  onChange={(e) => setBanReason(e.target.value)}
                  placeholder="Why is this user being banned?"
                  className="w-full bg-zinc-700 rounded-lg px-3 py-2 text-sm resize-none h-20"
                />
              </div>

              {/* Expiration (Site ban only) */}
              {banType === 'site' && (
                <div>
                  <label className="text-sm text-zinc-400 block mb-2">Expires (optional)</label>
                  <input
                    type="datetime-local"
                    value={banExpires}
                    onChange={(e) => setBanExpires(e.target.value)}
                    className="w-full bg-zinc-700 rounded-lg px-3 py-2 text-sm"
                  />
                  <p className="text-xs text-zinc-500 mt-1">
                    Leave empty for permanent ban
                  </p>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setBanModalOpen(false)}
                  className="flex-1 py-2 px-4 rounded-lg bg-zinc-700 hover:bg-zinc-600 text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={handleBan}
                  disabled={banLoading || !banReason.trim()}
                  className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium disabled:opacity-50 ${
                    banType === 'site'
                      ? 'bg-red-600 hover:bg-red-500'
                      : 'bg-orange-600 hover:bg-orange-500'
                  }`}
                >
                  {banLoading ? 'Banning...' : `Apply ${banType === 'site' ? 'Site' : 'Chat'} Ban`}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer Note */}
      <div className="max-w-5xl mx-auto px-4 py-8 text-center">
        <p className="text-zinc-500 text-sm">
          This is a read-only admin view. Actions taken here are logged.
        </p>
      </div>
    </div>
  );
}

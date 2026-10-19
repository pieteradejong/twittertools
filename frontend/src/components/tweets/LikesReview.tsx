import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';

const API = 'http://localhost:8000/api/likes-review';

// ---------- types (mirror src/likes_review.py) ----------
interface LikeItem {
  id: string;
  text: string;
  created_at: string | null;
  status: 'ok' | 'unavailable' | 'error' | 'pending';
  tweet_url: string;
  author: { id?: string; username?: string; display_name?: string; avatar_url?: string; verified: boolean };
  metrics: { like_count: number; reply_count: number; retweet_count: number };
  lang?: string;
  media_type: 'none' | 'photo' | 'video' | 'gif' | 'mixed' | 'unknown';
  has_video: boolean;
  has_photo: boolean;
  has_gif: boolean;
  video_duration_ms: number | null;
  media_urls: string[];
  urls: string[];
  url_domains: string[];
  hashtags: string[];
  is_reply: boolean;
  in_reply_to_username?: string;
  is_quote: boolean;
  quoted_author_username?: string;
  topics: string[];
}

interface ItemsResponse { total: number; limit: number; offset: number; items: LikeItem[] }
interface Bucket { key: string; count: number }
interface Summary {
  total: number;
  status: Bucket[];
  media_type: Bucket[];
  video_total_seconds: number;
  by_year: Bucket[];
  by_month: Bucket[];
  top_authors: Bucket[];
  languages: Bucket[];
  topics: Bucket[];
  top_domains: Bucket[];
}

interface Filters {
  q: string;
  author: string;
  media: string;
  topic: string;
  year: string;
  lang: string;
  domain: string;
  is_reply: string;   // '' | 'true' | 'false'
  is_quote: string;
  status: string;
  min_video_seconds: string;
  sort: string;
}

const EMPTY: Filters = {
  q: '', author: '', media: 'any', topic: '', year: '', lang: '', domain: '',
  is_reply: '', is_quote: '', status: '', min_video_seconds: '', sort: 'newest',
};

const PAGE_SIZE = 50;

function toParams(f: Filters, extra: Record<string, string | number> = {}) {
  const p = new URLSearchParams();
  Object.entries({ ...f, ...extra }).forEach(([k, v]) => {
    if (v !== '' && v !== undefined && v !== null && !(k === 'media' && v === 'any')) p.set(k, String(v));
  });
  return p.toString();
}

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

const fmtDuration = (ms: number) => {
  const s = Math.round(ms / 1000);
  const m = Math.floor(s / 60);
  return m ? `${m}:${String(s % 60).padStart(2, '0')}` : `0:${String(s).padStart(2, '0')}`;
};
const fmtDate = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '');
const fmtCount = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : String(n));

// ---------- small presentational pieces ----------
function Badge({ children, tone = 'gray', onClick, title }: { children: ReactNode; tone?: string; onClick?: () => void; title?: string }) {
  const tones: Record<string, string> = {
    gray: 'bg-gray-100 text-gray-700', red: 'bg-red-100 text-red-800', blue: 'bg-blue-100 text-blue-800',
    green: 'bg-green-100 text-green-800', purple: 'bg-purple-100 text-purple-800', amber: 'bg-amber-100 text-amber-800',
  };
  return (
    <span
      title={title}
      onClick={onClick}
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${tones[tone] ?? tones.gray} ${onClick ? 'cursor-pointer hover:opacity-80' : ''}`}
    >
      {children}
    </span>
  );
}

function BarList({ title, buckets, onPick, active, max = 8 }: { title: string; buckets: Bucket[]; onPick: (k: string) => void; active?: string; max?: number }) {
  const top = buckets.slice(0, max);
  const peak = Math.max(1, ...top.map((b) => b.count));
  return (
    <div className="min-w-[180px] flex-1">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{title}</div>
      {top.length === 0 && <div className="text-xs text-gray-400">—</div>}
      {top.map((b) => (
        <button
          key={b.key}
          onClick={() => onPick(active === b.key ? '' : b.key)}
          className={`w-full text-left text-xs py-0.5 group ${active === b.key ? 'text-blue-700 font-semibold' : 'text-gray-700'}`}
        >
          <div className="flex justify-between gap-2">
            <span className="truncate">{b.key}</span>
            <span className="text-gray-400 tabular-nums">{b.count}</span>
          </div>
          <div className="h-1 bg-gray-100 rounded">
            <div className={`h-1 rounded ${active === b.key ? 'bg-blue-500' : 'bg-gray-300 group-hover:bg-blue-300'}`} style={{ width: `${(b.count / peak) * 100}%` }} />
          </div>
        </button>
      ))}
    </div>
  );
}

function LikeCard({ it, onFilter }: { it: LikeItem; onFilter: (patch: Partial<Filters>) => void }) {
  const name = it.author.display_name || it.author.username || 'Unknown';
  const handle = it.author.username;
  const avatar = it.author.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=1da1f2&color=fff&size=40`;
  const unavailable = it.status !== 'ok';
  return (
    <div className={`border-b border-gray-200 p-3 hover:bg-gray-50 transition-colors ${unavailable ? 'opacity-70' : ''}`}>
      <div className="flex gap-3">
        <img src={avatar} alt={name} className="rounded-full w-10 h-10 object-cover flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1 flex-wrap text-sm">
            <span className="font-bold text-gray-900 truncate">{name}</span>
            {handle && (
              <button className="text-gray-500 hover:underline" onClick={() => onFilter({ author: handle })} title="Filter by author">@{handle}</button>
            )}
            <span className="text-gray-400">·</span>
            <span className="text-gray-500" title={it.created_at ?? ''}>{fmtDate(it.created_at)}</span>
            {unavailable && <Badge tone="amber" title="Tweet deleted, protected, or not fetched yet">{it.status}</Badge>}
            <a href={it.tweet_url} target="_blank" rel="noreferrer" className="ml-auto text-xs text-blue-600 hover:underline">Open on X ↗</a>
          </div>

          <div className="flex flex-wrap gap-1 mt-1 mb-2">
            {it.has_video && <Badge tone="red" onClick={() => onFilter({ media: 'video' })}>▶ video {it.video_duration_ms ? fmtDuration(it.video_duration_ms) : ''}</Badge>}
            {it.has_gif && <Badge tone="red">GIF</Badge>}
            {it.has_photo && <Badge tone="blue" onClick={() => onFilter({ media: 'photo' })}>🖼 photo{it.media_urls.length > 1 ? ` ×${it.media_urls.length}` : ''}</Badge>}
            {it.is_reply && <Badge tone="gray" title="This is a reply">↩ {it.in_reply_to_username ? `@${it.in_reply_to_username}` : 'reply'}</Badge>}
            {it.is_quote && <Badge tone="gray" title="Quote tweet">❝ {it.quoted_author_username ? `@${it.quoted_author_username}` : 'quote'}</Badge>}
            {it.lang && it.lang !== 'en' && <Badge tone="gray" onClick={() => onFilter({ lang: it.lang! })}>{it.lang}</Badge>}
            {it.topics.map((t) => (
              <Badge key={t} tone="purple" onClick={() => onFilter({ topic: t })}>{t}</Badge>
            ))}
          </div>

          <div className="text-gray-900 whitespace-pre-wrap break-words text-[15px]">{it.text}</div>

          {it.media_urls.length > 0 && (
            <div className={`mt-2 grid gap-1 ${it.media_urls.length > 1 ? 'grid-cols-2' : 'grid-cols-1'} max-w-lg`}>
              {it.media_urls.slice(0, 4).map((u, i) => (
                <a key={i} href={it.tweet_url} target="_blank" rel="noreferrer" className="relative block">
                  <img src={u} alt="" loading="lazy" className="rounded-lg border border-gray-200 w-full object-cover max-h-64" />
                  {it.has_video && i === 0 && (
                    <span className="absolute inset-0 flex items-center justify-center text-white text-3xl drop-shadow">▶</span>
                  )}
                </a>
              ))}
            </div>
          )}

          {it.url_domains.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {it.url_domains.map((d) => (
                <Badge key={d} tone="green" onClick={() => onFilter({ domain: d })}>🔗 {d}</Badge>
              ))}
            </div>
          )}

          <div className="mt-2 text-xs text-gray-500 flex gap-4">
            <span>♥ {fmtCount(it.metrics.like_count)}</span>
            <span>💬 {fmtCount(it.metrics.reply_count)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- main component ----------
export function LikesReview({ isActive }: { isActive: boolean }) {
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [page, setPage] = useState(0);
  const [showStats, setShowStats] = useState(true);
  const qc = useQueryClient();

  const debouncedQ = useDebounced(filters.q);
  const effective = useMemo(() => ({ ...filters, q: debouncedQ }), [filters, debouncedQ]);
  const patch = (p: Partial<Filters>) => { setFilters((f) => ({ ...f, ...p })); setPage(0); };

  const itemsQuery = useQuery({
    queryKey: ['likes-review', 'items', effective, page],
    queryFn: async () => (await axios.get<ItemsResponse>(`${API}/items?${toParams(effective, { limit: PAGE_SIZE, offset: page * PAGE_SIZE })}`)).data,
    enabled: isActive,
    staleTime: 5 * 60 * 1000,
    placeholderData: (prev) => prev,
  });

  const summaryQuery = useQuery({
    queryKey: ['likes-review', 'summary', effective],
    queryFn: async () => (await axios.get<Summary>(`${API}/summary?${toParams(effective)}`)).data,
    enabled: isActive,
    staleTime: 5 * 60 * 1000,
    placeholderData: (prev) => prev,
  });

  const retag = useMutation({
    mutationFn: async () => (await axios.post(`${API}/tag-topics`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['likes-review'] }),
  });

  const s = summaryQuery.data;
  const total = itemsQuery.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const mediaCount = (k: string) => s?.media_type.find((b) => b.key === k)?.count ?? 0;
  const statusCount = (k: string) => s?.status.find((b) => b.key === k)?.count ?? 0;
  const activeFilterCount = Object.entries(filters).filter(([k, v]) => v !== '' && !(k === 'media' && v === 'any') && k !== 'sort').length;

  if (itemsQuery.isError) {
    const msg = axios.isAxiosError(itemsQuery.error) ? (itemsQuery.error.response?.data?.detail ?? itemsQuery.error.message) : String(itemsQuery.error);
    return <ErrorState message={`Likes Review unavailable: ${String(msg)}`} onRetry={() => itemsQuery.refetch()} />;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-gray-200 p-3 space-y-2">
        <div className="flex flex-wrap gap-2 items-center">
          <input
            className="flex-1 min-w-[220px] px-3 py-1.5 border border-gray-300 rounded-md text-sm"
            placeholder="Search text or author…"
            value={filters.q}
            onChange={(e) => patch({ q: e.target.value })}
          />
          <select className="px-2 py-1.5 border border-gray-300 rounded-md text-sm" value={filters.media} onChange={(e) => patch({ media: e.target.value })}>
            <option value="any">All media</option>
            <option value="any-media">Has media</option>
            <option value="video">Video{s ? ` (${mediaCount('video') + mediaCount('mixed')})` : ''}</option>
            <option value="photo">Photo{s ? ` (${mediaCount('photo')})` : ''}</option>
            <option value="gif">GIF{s ? ` (${mediaCount('gif')})` : ''}</option>
            <option value="mixed">Mixed</option>
            <option value="none">Text only{s ? ` (${mediaCount('none')})` : ''}</option>
          </select>
          <select className="px-2 py-1.5 border border-gray-300 rounded-md text-sm" value={filters.topic} onChange={(e) => patch({ topic: e.target.value })}>
            <option value="">All topics</option>
            {s?.topics.map((t) => <option key={t.key} value={t.key}>{t.key} ({t.count})</option>)}
          </select>
          <select className="px-2 py-1.5 border border-gray-300 rounded-md text-sm" value={filters.year} onChange={(e) => patch({ year: e.target.value })}>
            <option value="">All years</option>
            {s?.by_year.map((y) => <option key={y.key} value={y.key}>{y.key} ({y.count})</option>)}
          </select>
          <select className="px-2 py-1.5 border border-gray-300 rounded-md text-sm" value={filters.sort} onChange={(e) => patch({ sort: e.target.value })}>
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="popular">Most liked</option>
            <option value="longest-video">Longest video</option>
          </select>
          <select className="px-2 py-1.5 border border-gray-300 rounded-md text-sm" value={filters.is_reply} onChange={(e) => patch({ is_reply: e.target.value })}>
            <option value="">Replies: any</option>
            <option value="false">Not replies</option>
            <option value="true">Replies only</option>
          </select>
          <select className="px-2 py-1.5 border border-gray-300 rounded-md text-sm" value={filters.status} onChange={(e) => patch({ status: e.target.value })}>
            <option value="">Status: any</option>
            <option value="ok">Fetched</option>
            <option value="unavailable">Unavailable</option>
            <option value="pending">Not fetched</option>
            <option value="error">Error</option>
          </select>
          {activeFilterCount > 0 && (
            <button className="text-sm text-blue-600 hover:underline" onClick={() => { setFilters({ ...EMPTY, sort: filters.sort }); setPage(0); }}>
              Clear {activeFilterCount} filter{activeFilterCount > 1 ? 's' : ''}
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2 items-center text-sm text-gray-600">
          <span className="font-medium text-gray-900">{total.toLocaleString()}</span> likes
          {filters.author && <Badge tone="blue" onClick={() => patch({ author: '' })}>@{filters.author} ✕</Badge>}
          {filters.domain && <Badge tone="green" onClick={() => patch({ domain: '' })}>{filters.domain} ✕</Badge>}
          {filters.lang && <Badge tone="gray" onClick={() => patch({ lang: '' })}>{filters.lang} ✕</Badge>}
          {filters.min_video_seconds && <Badge tone="red" onClick={() => patch({ min_video_seconds: '' })}>≥ {filters.min_video_seconds}s ✕</Badge>}
          <span className="ml-auto flex gap-2 items-center">
            <button className="text-blue-600 hover:underline" onClick={() => setShowStats((v) => !v)}>{showStats ? 'Hide' : 'Show'} stats</button>
            <span className="text-gray-300">|</span>
            <span>Export:</span>
            {(['csv', 'json', 'md'] as const).map((fmt) => (
              <a key={fmt} className="text-blue-600 hover:underline uppercase" href={`${API}/export?${toParams(effective, { format: fmt })}`} download>{fmt}</a>
            ))}
            <span className="text-gray-300">|</span>
            <button className="text-blue-600 hover:underline disabled:opacity-50" disabled={retag.isPending} onClick={() => retag.mutate()} title="Re-run keyword topic tagging (edit TOPIC_RULES in scripts/enrich_likes.py)">
              {retag.isPending ? 'Tagging…' : 'Re-tag topics'}
            </button>
          </span>
        </div>
      </div>

      {/* Stats panel — follows the current filters */}
      {showStats && s && (
        <div className="border-b border-gray-200 p-3 bg-gray-50">
          <div className="flex flex-wrap gap-3 mb-3 text-sm">
            <Stat label="Fetched" value={statusCount('ok')} sub={`${statusCount('unavailable')} unavailable · ${statusCount('pending')} pending`} />
            <Stat label="With video" value={mediaCount('video') + mediaCount('mixed')} sub={`${Math.round(s.video_total_seconds / 60)} min total`} onClick={() => patch({ media: 'video' })} />
            <Stat label="With photos" value={mediaCount('photo')} onClick={() => patch({ media: 'photo' })} />
            <Stat label="Text only" value={mediaCount('none')} onClick={() => patch({ media: 'none' })} />
          </div>
          <div className="flex flex-wrap gap-6">
            <BarList title="Top authors" buckets={s.top_authors} active={filters.author} onPick={(k) => patch({ author: k })} max={10} />
            <BarList title="Topics" buckets={s.topics} active={filters.topic} onPick={(k) => patch({ topic: k })} max={10} />
            <BarList title="Linked domains" buckets={s.top_domains} active={filters.domain} onPick={(k) => patch({ domain: k })} />
            <BarList title="By year" buckets={[...s.by_year].sort((a, b) => a.key.localeCompare(b.key))} active={filters.year} onPick={(k) => patch({ year: k })} max={15} />
            <BarList title="Languages" buckets={s.languages} active={filters.lang} onPick={(k) => patch({ lang: k })} max={6} />
          </div>
          <MonthSparkline buckets={s.by_month} />
        </div>
      )}

      {/* List */}
      <div className="flex-1 overflow-auto">
        {itemsQuery.isLoading && <LoadingState message="Loading likes…" />}
        {itemsQuery.data && itemsQuery.data.items.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            No likes match. {statusCount('ok') === 0 && 'Run `python scripts/enrich_likes.py --all` to fetch details.'}
          </div>
        )}
        {itemsQuery.data?.items.map((it) => <LikeCard key={it.id} it={it} onFilter={patch} />)}
        {pages > 1 && (
          <div className="flex justify-between items-center p-4 text-sm">
            <button className="px-3 py-1.5 rounded bg-gray-100 border border-gray-300 disabled:opacity-50" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <span className="text-gray-500">Page {page + 1} of {pages}</span>
            <button className="px-3 py-1.5 rounded bg-gray-100 border border-gray-300 disabled:opacity-50" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, sub, onClick }: { label: string; value: number; sub?: string; onClick?: () => void }) {
  return (
    <button onClick={onClick} disabled={!onClick} className="text-left bg-white border border-gray-200 rounded-lg px-3 py-2 min-w-[130px] hover:border-blue-300 disabled:hover:border-gray-200">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-lg font-semibold text-gray-900 tabular-nums">{value.toLocaleString()}</div>
      {sub && <div className="text-xs text-gray-400">{sub}</div>}
    </button>
  );
}

function MonthSparkline({ buckets }: { buckets: Bucket[] }) {
  if (buckets.length < 2) return null;
  const peak = Math.max(1, ...buckets.map((b) => b.count));
  return (
    <div className="mt-3">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Likes per month (by tweet date)</div>
      <div className="flex items-end gap-px h-12">
        {buckets.map((b) => (
          <div key={b.key} title={`${b.key}: ${b.count}`} className="flex-1 bg-blue-300 hover:bg-blue-500 rounded-t" style={{ height: `${(b.count / peak) * 100}%`, minWidth: 2 }} />
        ))}
      </div>
      <div className="flex justify-between text-[10px] text-gray-400"><span>{buckets[0].key}</span><span>{buckets[buckets.length - 1].key}</span></div>
    </div>
  );
}

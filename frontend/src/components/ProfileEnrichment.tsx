import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

interface ProfileStats {
  users: {
    total: number;
    with_api_profiles: number;
    with_local_profiles: number;
    with_usernames: number;
    with_avatars: number;
    verified: number;
  };
  last_enrichment: string | null;
  enrichment_progress: {
    total_processed: number;
    last_batch_size: number;
    estimated_time_remaining: string | null;
  };
}

interface EnrichmentResult {
  message: string;
  stats: {
    profiles_enriched: number;
    api_calls_made: number;
    rate_limit_remaining: number;
    total_processed: number;
  };
}

interface ScrapeResult {
  message: string;
  total_requested: number;
  successfully_scraped: number;
  failed_scrapes: number;
  profiles_updated: number;
  errors: string[];
}

async function fetchProfileStats(): Promise<ProfileStats> {
  const { data } = await axios.get('http://localhost:8000/api/profiles/stats');
  return data;
}

async function enrichProfiles(limit: number): Promise<EnrichmentResult> {
  const { data } = await axios.post(`http://localhost:8000/api/profiles/enrich?limit=${limit}`);
  return data;
}

async function scrapeProfiles(limit: number, delay: number): Promise<ScrapeResult> {
  const { data } = await axios.post(`http://localhost:8000/api/profiles/scrape?limit=${limit}&delay=${delay}`);
  return data;
}

export function ProfileEnrichment() {
  const [batchSize, setBatchSize] = useState(50);
  const [scrapeDelay, setScrapeDelay] = useState(2.0);
  const queryClient = useQueryClient();
  
  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['profileStats'],
    queryFn: fetchProfileStats,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const enrichmentMutation = useMutation({
    mutationFn: enrichProfiles,
    onSuccess: () => {
      // Invalidate and refetch stats
      queryClient.invalidateQueries({ queryKey: ['profileStats'] });
      queryClient.invalidateQueries({ queryKey: ['followers'] });
      queryClient.invalidateQueries({ queryKey: ['following'] });
    },
  });

  const scrapeMutation = useMutation({
    mutationFn: ({ limit, delay }: { limit: number; delay: number }) => 
      scrapeProfiles(limit, delay),
    onSuccess: () => {
      // Invalidate and refetch stats
      queryClient.invalidateQueries({ queryKey: ['profileStats'] });
      queryClient.invalidateQueries({ queryKey: ['followers'] });
      queryClient.invalidateQueries({ queryKey: ['following'] });
    },
  });

  const handleEnrichment = () => {
    enrichmentMutation.mutate(batchSize);
  };

  const handleScraping = () => {
    scrapeMutation.mutate({ limit: batchSize, delay: scrapeDelay });
  };

  if (statsLoading) {
    return (
      <div className="bg-white rounded-xl shadow p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            <div className="h-4 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          </div>
        </div>
      </div>
    );
  }

  if (statsError) {
    return (
      <div className="bg-white rounded-xl shadow p-6">
        <div className="text-center">
          <div className="text-red-600 mb-4">❌ Error loading profile stats</div>
          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ['profileStats'] })}
            className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-md text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const missingProfiles = stats!.users.total - stats!.users.with_usernames;
  const enrichmentProgress = Math.round((stats!.users.with_usernames / stats!.users.total) * 100);

  return (
    <div className="bg-white rounded-xl shadow">
      <div className="p-6 border-b border-gray-200">
        <h2 className="text-xl font-semibold text-gray-900">Profile Enrichment</h2>
        <p className="text-gray-600 text-sm mt-1">
          Fetch real usernames, avatars, and profile data using Twitter API or web scraping
        </p>
      </div>

      <div className="p-6 space-y-6">
        {/* Stats Overview */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{stats!.users.total}</div>
            <div className="text-sm text-gray-500">Total Users</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{stats!.users.with_usernames}</div>
            <div className="text-sm text-gray-500">Have Usernames</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-orange-600">{missingProfiles}</div>
            <div className="text-sm text-gray-500">Need Profiles</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">{stats!.users.verified}</div>
            <div className="text-sm text-gray-500">Verified</div>
          </div>
        </div>

        {/* Progress Bar */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">Enrichment Progress</span>
            <span className="text-sm text-gray-500">{enrichmentProgress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${enrichmentProgress}%` }}
            ></div>
          </div>
        </div>

        {/* Enrichment Controls */}
        <div className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-medium text-gray-900">Batch Enrichment</h3>
              <p className="text-sm text-gray-600">
                Fetch profile data using Twitter API (requires valid API credentials)
              </p>
            </div>
            <div className="flex items-center gap-3">
              <label htmlFor="batchSize" className="text-sm text-gray-700">
                Batch size:
              </label>
              <select
                id="batchSize"
                value={batchSize}
                onChange={(e) => setBatchSize(Number(e.target.value))}
                className="border border-gray-300 rounded-md px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={enrichmentMutation.isPending}
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleEnrichment}
            disabled={enrichmentMutation.isPending || missingProfiles === 0}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium transition-colors"
          >
            {enrichmentMutation.isPending ? (
              <span className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                Enriching profiles...
              </span>
            ) : missingProfiles === 0 ? (
              'All profiles enriched!'
            ) : (
              `Enrich ${Math.min(batchSize, missingProfiles)} profiles`
            )}
          </button>

          {enrichmentMutation.isError && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-700">
                ❌ Enrichment failed. This usually means:
              </p>
              <ul className="text-sm text-red-600 mt-1 ml-4 list-disc">
                <li>Twitter API credentials are not configured</li>
                <li>API rate limits have been exceeded</li>
                <li>Twitter API access has been suspended</li>
              </ul>
            </div>
          )}

          {enrichmentMutation.isSuccess && enrichmentMutation.data && (
            <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-md">
              <p className="text-sm text-green-700">
                ✅ {enrichmentMutation.data.message}
              </p>
              <div className="text-sm text-green-600 mt-1">
                • {enrichmentMutation.data.stats.profiles_enriched} profiles enriched
                • {enrichmentMutation.data.stats.api_calls_made} API calls made
                • {enrichmentMutation.data.stats.rate_limit_remaining} API calls remaining
              </div>
            </div>
          )}
        </div>

        {/* Web Scraping Controls */}
        <div className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-medium text-gray-900">Web Scraping (No API Required)</h3>
              <p className="text-sm text-gray-600">
                Scrape public profile data directly from Twitter web pages
              </p>
            </div>
            <div className="flex items-center gap-3">
              <label htmlFor="scrapeDelay" className="text-sm text-gray-700">
                Delay (sec):
              </label>
              <select
                id="scrapeDelay"
                value={scrapeDelay}
                onChange={(e) => setScrapeDelay(Number(e.target.value))}
                className="border border-gray-300 rounded-md px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                disabled={scrapeMutation.isPending}
              >
                <option value={1.0}>1.0</option>
                <option value={2.0}>2.0</option>
                <option value={3.0}>3.0</option>
                <option value={5.0}>5.0</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleScraping}
            disabled={scrapeMutation.isPending || missingProfiles === 0}
            className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium transition-colors"
          >
            {scrapeMutation.isPending ? (
              <span className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                Scraping profiles...
              </span>
            ) : missingProfiles === 0 ? (
              'All profiles have data!'
            ) : (
              `Scrape ${Math.min(batchSize, missingProfiles)} profiles`
            )}
          </button>

          {scrapeMutation.isError && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-700">
                ❌ Web scraping failed. This might be due to:
              </p>
              <ul className="text-sm text-red-600 mt-1 ml-4 list-disc">
                <li>Twitter requires JavaScript for profile pages</li>
                <li>Anti-bot protection blocking automated access</li>
                <li>Profile pages requiring authentication</li>
                <li>Network connectivity issues</li>
              </ul>
              <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
                <strong>💡 Alternatives:</strong>
                <ul className="mt-1 ml-4 list-disc">
                  <li>Use the "View Profile" links to visit profiles manually</li>
                  <li>Copy usernames from profile pages and add them to the database</li>
                  <li>Wait for Twitter API access (recommended for bulk operations)</li>
                </ul>
              </div>
            </div>
          )}

          {scrapeMutation.isSuccess && scrapeMutation.data && (
            <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-md">
              <p className="text-sm text-amber-700">
                ⚠️ Web scraping completed with limitations:
              </p>
              <div className="text-sm text-amber-600 mt-1">
                • {scrapeMutation.data.successfully_scraped} profiles scraped successfully
                • {scrapeMutation.data.failed_scrapes} profiles failed to scrape
                • {scrapeMutation.data.profiles_updated} database records updated
              </div>
              {scrapeMutation.data.errors.length > 0 && (
                <details className="mt-2">
                  <summary className="text-sm text-gray-600 cursor-pointer">View errors ({scrapeMutation.data.errors.length})</summary>
                  <div className="mt-1 text-xs text-gray-500 max-h-32 overflow-y-auto">
                    {scrapeMutation.data.errors.map((error, index) => (
                      <div key={index}>• {error}</div>
                    ))}
                  </div>
                </details>
              )}
              <div className="mt-2 text-xs text-amber-600">
                <strong>Note:</strong> Twitter heavily restricts automated access to profile data. 
                For reliable results, consider using the Twitter API instead.
              </div>
            </div>
          )}
        </div>

        {/* Help Text */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="font-medium text-blue-900 mb-2">💡 Profile Data Options</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-blue-800">
            <div>
              <h5 className="font-medium mb-1">🔑 API Enrichment (Recommended)</h5>
              <ul className="space-y-1">
                <li>• Requires Twitter API access ($200/month)</li>
                <li>• Gets comprehensive profile data</li>
                <li>• Includes follower counts & verification</li>
                <li>• Fast batch processing (100 users/call)</li>
                <li>• Reliable and supported by Twitter</li>
              </ul>
            </div>
            <div>
              <h5 className="font-medium mb-1">🕷️ Web Scraping (Limited)</h5>
              <ul className="space-y-1">
                <li>• No API access required (free)</li>
                <li>• <span className="text-red-600">⚠️ Blocked by Twitter's anti-bot measures</span></li>
                <li>• <span className="text-red-600">⚠️ Requires JavaScript for modern profiles</span></li>
                <li>• May violate Twitter's Terms of Service</li>
                <li>• Better for manual profile visiting</li>
              </ul>
            </div>
          </div>
          
          <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
            <h5 className="font-medium text-green-900 mb-1">📋 Manual Workflow (Current Best Option)</h5>
            <p className="text-sm text-green-800">
              While automated scraping is limited, you can still enrich profile data manually:
            </p>
            <ol className="text-sm text-green-700 mt-2 ml-4 list-decimal space-y-1">
              <li>Use the "View Profile" buttons in Followers/Following pages</li>
              <li>Copy usernames from the profile pages you visit</li>
              <li>Manually add usernames to improve the display</li>
              <li>Use API enrichment when credentials become available</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
} 
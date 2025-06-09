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

async function fetchProfileStats(): Promise<ProfileStats> {
  const { data } = await axios.get('http://localhost:8000/api/profiles/stats');
  return data;
}

async function enrichProfiles(limit: number): Promise<EnrichmentResult> {
  const { data } = await axios.post(`http://localhost:8000/api/profiles/enrich?limit=${limit}`);
  return data;
}

export function ProfileEnrichment() {
  const [batchSize, setBatchSize] = useState(50);
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

  const handleEnrichment = () => {
    enrichmentMutation.mutate(batchSize);
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
          Fetch real usernames, avatars, and profile data using Twitter API
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

        {/* API Enrichment Controls */}
        <div className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-medium text-gray-900">API Enrichment</h3>
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

          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              {missingProfiles === 0 
                ? "🎉 All profiles have been enriched!" 
                : `${missingProfiles} profiles need enrichment`
              }
            </div>
            <button
              onClick={handleEnrichment}
              disabled={enrichmentMutation.isPending || missingProfiles === 0}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium transition-colors"
            >
              {enrichmentMutation.isPending ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Enriching...
                </div>
              ) : (
                `Enrich ${Math.min(batchSize, missingProfiles)} profiles`
              )}
            </button>
          </div>

          {enrichmentMutation.isError && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
              <div className="text-sm text-red-800">
                ❌ API enrichment failed. This might be due to:
                <ul className="mt-2 ml-4 list-disc text-xs space-y-1">
                  <li>Missing or invalid Twitter API credentials</li>
                  <li>API rate limit exceeded (300 requests per 15 minutes)</li>
                  <li>Network connectivity issues</li>
                  <li>Twitter API service unavailable</li>
                </ul>
              </div>
            </div>
          )}

          {enrichmentMutation.isSuccess && enrichmentMutation.data && (
            <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
              <div className="text-sm text-green-800">
                ✅ API enrichment completed successfully:
                <ul className="mt-2 ml-4 list-disc text-xs space-y-1">
                  <li>{enrichmentMutation.data.stats.profiles_enriched} profiles enriched</li>
                  <li>{enrichmentMutation.data.stats.api_calls_made} API calls made</li>
                  <li>{enrichmentMutation.data.stats.rate_limit_remaining} requests remaining</li>
                </ul>
              </div>
            </div>
          )}
        </div>

        {/* Information Panel */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="font-medium text-blue-900 mb-3">📋 Profile Enrichment Guide</h4>
          
          <div className="space-y-4 text-sm text-blue-800">
            <div>
              <h5 className="font-medium mb-1">🔑 API Requirements</h5>
              <p className="text-xs leading-relaxed">
                To fetch real profile data, you need Twitter API Basic tier access ($200/month). 
                The user lookup endpoint can fetch up to 100 users per request, and you have 
                300 requests per 15-minute window.
              </p>
            </div>

            <div>
              <h5 className="font-medium mb-1">⚡ How It Works</h5>
              <p className="text-xs leading-relaxed">
                The enrichment process fetches usernames, display names, profile photos, 
                verification status, and bio information for users in your followers/following 
                lists who currently show as "Twitter User XXXXX".
              </p>
            </div>

            <div>
              <h5 className="font-medium mb-1">📊 Current Status</h5>
              <p className="text-xs leading-relaxed">
                You have {stats!.users.total} total users in your network. 
                {stats!.users.with_usernames} have real usernames, 
                {missingProfiles} still need profile data. 
                For complete enrichment of {missingProfiles} users, you would need about {Math.ceil(missingProfiles / 100)} API calls.
              </p>
            </div>

            <div>
              <h5 className="font-medium mb-1">💡 Alternative Options</h5>
              <p className="text-xs leading-relaxed">
                If you don't have API access, you can manually check profiles using the 
                "View Profile" buttons in the Following/Followers tabs, or wait until 
                you obtain API credentials.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 
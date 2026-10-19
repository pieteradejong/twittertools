import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import axios from 'axios';
// Note: Using placeholder icons - install @heroicons/react for proper icons
// import { UserGroupIcon, TagIcon, SparklesIcon } from '@heroicons/react/24/outline';

interface ClassificationMethod {
  name: string;
  description: string;
  pros: string[];
  cons: string[];
}

interface AccountClassification {
  user_id: string;
  username: string;
  display_name: string;
  primary_topics: string[];
  topic_scores: Record<string, number>;
  profile_category: string;
  engagement_score: number;
  suggested_lists: string[];
  confidence_score: number;
  classification_reasons: string[];
}

interface ListSuggestion {
  list_name: string;
  description: string;
  category: string;
  confidence_score: number;
  creation_reason: string;
  member_count: number;
  members: Array<{
    id: string;
    username: string;
    display_name: string;
    primary_topics: string[];
    profile_category: string;
    confidence_score: number;
  }>;
}

interface AccountClassifierProps {
  isActive: boolean;
}

export function AccountClassifier({ isActive }: AccountClassifierProps) {
  const [selectedMethod, setSelectedMethod] = useState('hybrid');
  const [minMembersPerList, setMinMembersPerList] = useState(3);
  const [maxLists, setMaxLists] = useState(15);
  const [limit, setLimit] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<'classify' | 'suggestions'>('suggestions');

  // Fetch available methods
  const { data: methodsData } = useQuery({
    queryKey: ['classification-methods'],
    queryFn: () => axios.get('http://localhost:8000/api/accounts/classification-methods').then(res => res.data),
    enabled: isActive,
  });

  // Classify accounts mutation
  const classifyMutation = useMutation({
    mutationFn: async (params: { method: string; limit?: number }) => {
      const response = await axios.post('http://localhost:8000/api/accounts/classify', params);
      return response.data;
    },
  });

  // Generate list suggestions mutation
  const suggestListsMutation = useMutation({
    mutationFn: async (params: {
      method: string;
      min_members_per_list: number;
      max_lists: number;
      limit?: number;
    }) => {
      const response = await axios.post('http://localhost:8000/api/accounts/suggest-lists', params);
      return response.data;
    },
  });

  const handleClassify = () => {
    classifyMutation.mutate({
      method: selectedMethod,
      limit: limit || undefined,
    });
  };

  const handleSuggestLists = () => {
    suggestListsMutation.mutate({
      method: selectedMethod,
      min_members_per_list: minMembersPerList,
      max_lists: maxLists,
      limit: limit || undefined,
    });
  };

  if (!isActive) return null;

  const methods = methodsData?.methods || {};
  const classifications = classifyMutation.data?.classifications || [];
  const suggestions = suggestListsMutation.data?.suggestions || [];

  return (
    <div className="max-w-6xl mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Account Classification</h1>
        <p className="text-gray-600">
          Automatically classify accounts you follow into meaningful lists based on content, profile, and engagement patterns.
        </p>
      </div>

      {/* Method Selection */}
      <div className="bg-white rounded-xl shadow mb-6 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Classification Settings</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Classification Method
            </label>
            <select
              value={selectedMethod}
              onChange={(e) => setSelectedMethod(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {Object.entries(methods).map(([key, method]) => (
                <option key={key} value={key}>
                  {(method as ClassificationMethod).name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Min Members per List
            </label>
            <input
              type="number"
              value={minMembersPerList}
              onChange={(e) => setMinMembersPerList(parseInt(e.target.value))}
              min="1"
              max="20"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Max Lists
            </label>
            <input
              type="number"
              value={maxLists}
              onChange={(e) => setMaxLists(parseInt(e.target.value))}
              min="1"
              max="50"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Account Limit (optional)
            </label>
            <input
              type="number"
              value={limit || ''}
              onChange={(e) => setLimit(e.target.value ? parseInt(e.target.value) : null)}
              placeholder="All accounts"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Method Description */}
        {methods[selectedMethod] && (
          <div className="bg-blue-50 rounded-lg p-4 mb-6">
            <h3 className="font-medium text-blue-900 mb-2">{methods[selectedMethod].name}</h3>
            <p className="text-blue-800 text-sm mb-3">{methods[selectedMethod].description}</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium text-green-700">Pros:</span>
                <ul className="list-disc list-inside text-green-600 mt-1">
                  {methods[selectedMethod].pros.map((pro: string, index: number) => (
                    <li key={index}>{pro}</li>
                  ))}
                </ul>
              </div>
              <div>
                <span className="font-medium text-orange-700">Cons:</span>
                <ul className="list-disc list-inside text-orange-600 mt-1">
                  {methods[selectedMethod].cons.map((con: string, index: number) => (
                    <li key={index}>{con}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-4">
          <button
            onClick={handleSuggestLists}
            disabled={suggestListsMutation.isPending}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            ✨
            {suggestListsMutation.isPending ? 'Generating...' : 'Generate List Suggestions'}
          </button>
          
          <button
            onClick={handleClassify}
            disabled={classifyMutation.isPending}
            className="flex items-center gap-2 px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            🏷️
            {classifyMutation.isPending ? 'Classifying...' : 'Classify Accounts'}
          </button>
        </div>
      </div>

      {/* Results Tabs */}
      <div className="bg-white rounded-xl shadow">
        <div className="border-b border-gray-200">
          <nav className="flex">
            <button
              onClick={() => setActiveTab('suggestions')}
              className={`px-6 py-4 text-sm font-medium border-b-2 ${
                activeTab === 'suggestions'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <div className="flex items-center gap-2">
                👥
                List Suggestions ({suggestions.length})
              </div>
            </button>
            <button
              onClick={() => setActiveTab('classify')}
              className={`px-6 py-4 text-sm font-medium border-b-2 ${
                activeTab === 'classify'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <div className="flex items-center gap-2">
                🏷️
                Classifications ({classifications.length})
              </div>
            </button>
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'suggestions' && (
            <div>
              {suggestions.length === 0 ? (
                <div className="text-center py-12">
                  <div className="text-6xl text-gray-400 mx-auto mb-4">👥</div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No List Suggestions Yet</h3>
                  <p className="text-gray-500 mb-4">
                    Click "Generate List Suggestions" to analyze your following accounts and create suggested lists.
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  {suggestions.map((suggestion: ListSuggestion, index: number) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-6">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900">{suggestion.list_name}</h3>
                          <p className="text-gray-600 text-sm mt-1">{suggestion.description}</p>
                        </div>
                        <div className="text-right">
                          <div className="text-sm text-gray-500">Confidence</div>
                          <div className="text-lg font-semibold text-blue-600">
                            {(suggestion.confidence_score * 100).toFixed(0)}%
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-4 text-sm text-gray-600 mb-4">
                        <span className="bg-gray-100 px-2 py-1 rounded">
                          {suggestion.category}
                        </span>
                        <span>{suggestion.member_count} members</span>
                      </div>
                      
                      <p className="text-sm text-gray-700 mb-4">{suggestion.creation_reason}</p>
                      
                      {/* Sample Members */}
                      <div>
                        <h4 className="text-sm font-medium text-gray-900 mb-2">Sample Members:</h4>
                        <div className="flex flex-wrap gap-2">
                          {suggestion.members.slice(0, 6).map((member, memberIndex) => (
                            <span
                              key={memberIndex}
                              className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                            >
                              {member.display_name}
                            </span>
                          ))}
                          {suggestion.members.length > 6 && (
                            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                              +{suggestion.members.length - 6} more
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'classify' && (
            <div>
              {classifications.length === 0 ? (
                <div className="text-center py-12">
                  <div className="text-6xl text-gray-400 mx-auto mb-4">🏷️</div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No Classifications Yet</h3>
                  <p className="text-gray-500 mb-4">
                    Click "Classify Accounts" to analyze individual accounts and see their classifications.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {classifications.map((classification: AccountClassification, index: number) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-900">{classification.display_name}</h3>
                          <p className="text-gray-600 text-sm">@{classification.username}</p>
                          
                          <div className="mt-2 flex flex-wrap gap-2">
                            {classification.profile_category !== 'unknown' && (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                {classification.profile_category.replace('_', ' ')}
                              </span>
                            )}
                            {classification.primary_topics.map((topic, topicIndex) => (
                              <span
                                key={topicIndex}
                                className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                              >
                                {topic}
                              </span>
                            ))}
                          </div>
                          
                          <div className="mt-2 text-xs text-gray-500">
                            Suggested lists: {classification.suggested_lists.join(', ')}
                          </div>
                        </div>
                        
                        <div className="text-right ml-4">
                          <div className="text-xs text-gray-500">Confidence</div>
                          <div className="text-sm font-semibold text-blue-600">
                            {(classification.confidence_score * 100).toFixed(0)}%
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 
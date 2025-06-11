import React from 'react';
import { ListMembersList } from './ListMembersList';

export const ListMembersDemo: React.FC = () => {
  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Twitter List Members Demo
        </h1>
        <p className="text-gray-600">
          Showcasing the list members functionality with sample data
        </p>
      </div>

      <div className="grid gap-8">
        {/* Tech Leaders List */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Tech Leaders List
          </h2>
          <ListMembersList listId="list_tech_leaders" isActive={true} />
        </div>

        {/* AI Researchers List */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            AI Researchers List
          </h2>
          <ListMembersList listId="list_ai_researchers" isActive={true} />
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="text-sm font-medium text-blue-900 mb-2">
          💡 Implementation Notes
        </h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• Data is fetched from the local SQLite database</li>
          <li>• Profile links use smart URL fallbacks (user_link → username → intent URL)</li>
          <li>• Verification badges and protected account indicators are shown</li>
          <li>• Rich profile data includes bio, location, follower counts, and profile images</li>
          <li>• Components use React Query for caching and error handling</li>
        </ul>
      </div>
    </div>
  );
}; 
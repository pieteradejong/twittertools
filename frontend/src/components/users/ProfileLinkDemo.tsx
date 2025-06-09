
import { 
  ProfileLink, 
  ProfileLinkButton, 
  ProfileLinkMinimal, 
  ProfileLinkWithOptions 
} from '../common/ProfileLink';

export function ProfileLinkDemo() {
  // Sample user data representing different scenarios
  const users = [
    {
      id: '12345',
      username: 'elonmusk',
      user_link: 'https://twitter.com/elonmusk',
      display_name: 'Elon Musk'
    },
    {
      id: '67890',
      username: 'jack',
      user_link: null,
      display_name: 'Jack Dorsey'
    },
    {
      id: '11111',
      username: null,
      user_link: 'https://twitter.com/someuser',
      display_name: 'User with custom link'
    },
    {
      id: '22222',
      username: null,
      user_link: null,
      display_name: 'User with only ID'
    }
  ];

  return (
    <div className="max-w-4xl mx-auto py-8">
      <h1 className="text-2xl font-bold mb-6">Profile Link Demo</h1>
      
      <div className="space-y-8">
        {users.map((user) => (
          <div key={user.id} className="bg-white p-6 rounded-lg shadow border">
            <h3 className="text-lg font-semibold mb-4">
              {user.display_name} 
              <span className="text-sm text-gray-500 ml-2">
                (ID: {user.id}, Username: {user.username || 'none'})
              </span>
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Default Link</h4>
                <ProfileLink user={user} />
              </div>
              
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Button Style</h4>
                <ProfileLinkButton user={user} />
              </div>
              
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Minimal Style</h4>
                <ProfileLinkMinimal user={user} />
              </div>
              
              <div>
                <h4 className="font-medium text-gray-700 mb-2">With Options</h4>
                <ProfileLinkWithOptions user={user} />
              </div>
            </div>
            
            <div className="mt-4 p-3 bg-gray-50 rounded text-sm">
              <strong>Generated URL:</strong> 
              <code className="ml-2 text-blue-600">
                {user.user_link || 
                 (user.username ? `https://twitter.com/${user.username}` : 
                  `https://twitter.com/intent/user?user_id=${user.id}`)}
              </code>
            </div>
          </div>
        ))}
      </div>
      
      <div className="mt-8 p-6 bg-blue-50 rounded-lg">
        <h3 className="text-lg font-semibold text-blue-900 mb-3">How Profile Links Work</h3>
        <ul className="space-y-2 text-blue-800">
          <li><strong>Priority 1:</strong> Use existing user_link if available</li>
          <li><strong>Priority 2:</strong> Generate twitter.com/username if username exists</li>
          <li><strong>Priority 3:</strong> Fall back to Twitter intent URL with user ID</li>
          <li><strong>Options variant:</strong> Shows dropdown with Twitter.com, X.com, and Intent links</li>
        </ul>
      </div>
    </div>
  );
} 
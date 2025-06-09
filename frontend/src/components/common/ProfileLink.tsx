import React from 'react';
import { generateProfileUrl, generateProfileLinkOptions } from '../../utils/profileLinks';
import type { UserProfile } from '../../utils/profileLinks';

interface ProfileLinkProps {
  user: UserProfile;
  children?: React.ReactNode;
  className?: string;
  showMultipleOptions?: boolean;
  variant?: 'default' | 'button' | 'minimal';
}

export function ProfileLink({ 
  user, 
  children, 
  className = '',
  showMultipleOptions = false,
  variant = 'default'
}: ProfileLinkProps) {
  const profileUrl = generateProfileUrl(user);
  const linkOptions = generateProfileLinkOptions(user);
  
  const baseClasses = {
    default: 'text-blue-600 hover:text-blue-800 hover:underline',
    button: 'inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-md transition-colors',
    minimal: 'text-gray-600 hover:text-gray-800'
  };

  const linkClass = `${baseClasses[variant]} ${className}`;

  // Default content if no children provided
  const defaultContent = children || (
    <>
      <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0 1 1 0 00-1.414 1.414 4 4 0 005.656 0l3-3a4 4 0 00-5.656-5.656l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5z" clipRule="evenodd" />
        <path fillRule="evenodd" d="M7.414 15.414a2 2 0 01-2.828-2.828l3-3a2 2 0 012.828 0 1 1 0 001.414-1.414 4 4 0 00-5.656 0l-3 3a4 4 0 105.656 5.656l1.5-1.5a1 1 0 00-1.414-1.414l-1.5 1.5z" clipRule="evenodd" />
      </svg>
      View Profile
    </>
  );

  if (showMultipleOptions && user.username) {
    return (
      <div className="flex items-center gap-2">
        <a
          href={profileUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={linkClass}
          title={`View @${user.username}'s profile`}
        >
          {defaultContent}
        </a>
        
        {/* Dropdown for additional options */}
        <div className="relative group">
          <button className="text-gray-400 hover:text-gray-600 p-1">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
            </svg>
          </button>
          
          <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-md shadow-lg border border-gray-200 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-10">
            <div className="py-1">
              <a
                href={linkOptions.username}
                target="_blank"
                rel="noopener noreferrer"
                className="block px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                Twitter.com
              </a>
              {linkOptions.x_domain && (
                <a
                  href={linkOptions.x_domain}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  X.com
                </a>
              )}
              <a
                href={linkOptions.intent}
                target="_blank"
                rel="noopener noreferrer"
                className="block px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                Twitter Intent
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <a
      href={profileUrl}
      target="_blank"
      rel="noopener noreferrer"
      className={linkClass}
      title={user.username ? `View @${user.username}'s profile` : `View profile for user ${user.id}`}
    >
      {defaultContent}
    </a>
  );
}

// Specialized variants for common use cases
export function ProfileLinkButton({ user, className = '' }: { user: UserProfile; className?: string }) {
  return (
    <ProfileLink 
      user={user} 
      variant="button" 
      className={className}
    />
  );
}

export function ProfileLinkMinimal({ user, className = '' }: { user: UserProfile; className?: string }) {
  return (
    <ProfileLink 
      user={user} 
      variant="minimal" 
      className={className}
    >
      @{user.username || user.id.slice(-8)}
    </ProfileLink>
  );
}

export function ProfileLinkWithOptions({ user, className = '' }: { user: UserProfile; className?: string }) {
  return (
    <ProfileLink 
      user={user} 
      showMultipleOptions={true}
      className={className}
    />
  );
} 
/**
 * Utility functions for generating Twitter profile links
 */

export interface UserProfile {
  id: string;
  username?: string | null;
  user_link?: string | null;
}

/**
 * Generate a Twitter profile URL for a user
 * Priority order:
 * 1. Use existing user_link if available
 * 2. Use username to create twitter.com/username link
 * 3. Fall back to Twitter intent URL with user ID
 */
export function generateProfileUrl(user: UserProfile): string {
  // First priority: use existing user_link
  if (user.user_link) {
    return user.user_link;
  }
  
  // Second priority: use username for clean URL
  if (user.username) {
    return `https://twitter.com/${user.username}`;
  }
  
  // Fallback: use Twitter intent URL with user ID
  return `https://twitter.com/intent/user?user_id=${user.id}`;
}

/**
 * Generate multiple profile link options for a user
 */
export function generateProfileLinkOptions(user: UserProfile): {
  primary: string;
  username?: string;
  intent: string;
  x_domain?: string;
} {
  const options = {
    primary: generateProfileUrl(user),
    intent: `https://twitter.com/intent/user?user_id=${user.id}`
  };

  // Add username-based link if available
  if (user.username) {
    return {
      ...options,
      username: `https://twitter.com/${user.username}`,
      x_domain: `https://x.com/${user.username}` // New X.com domain
    };
  }

  return options;
}

/**
 * Check if a profile link is valid/accessible
 */
export function isValidProfileLink(url: string): boolean {
  try {
    const parsedUrl = new URL(url);
    const validDomains = ['twitter.com', 'x.com'];
    return validDomains.includes(parsedUrl.hostname);
  } catch {
    return false;
  }
}

/**
 * Extract username from a Twitter URL
 */
export function extractUsernameFromUrl(url: string): string | null {
  try {
    const parsedUrl = new URL(url);
    if (parsedUrl.hostname === 'twitter.com' || parsedUrl.hostname === 'x.com') {
      const pathParts = parsedUrl.pathname.split('/').filter(Boolean);
      if (pathParts.length > 0 && !pathParts[0].startsWith('intent')) {
        return pathParts[0];
      }
    }
  } catch {
    // Invalid URL
  }
  return null;
}

/**
 * Generate a profile link with analytics tracking (optional)
 */
export function generateTrackedProfileUrl(
  user: UserProfile, 
  source: string = 'twittertools'
): string {
  const baseUrl = generateProfileUrl(user);
  
  // Add UTM parameters for tracking if it's a direct Twitter link
  if (baseUrl.includes('twitter.com') && user.username) {
    const url = new URL(baseUrl);
    url.searchParams.set('utm_source', source);
    url.searchParams.set('utm_medium', 'profile_link');
    return url.toString();
  }
  
  return baseUrl;
}

/**
 * Batch generate profile URLs for multiple users
 */
export function batchGenerateProfileUrls(users: UserProfile[]): Map<string, string> {
  const urlMap = new Map<string, string>();
  
  users.forEach(user => {
    urlMap.set(user.id, generateProfileUrl(user));
  });
  
  return urlMap;
}

/**
 * Profile link component props helper
 */
export interface ProfileLinkProps {
  href: string;
  isExternal: boolean;
  hasUsername: boolean;
  linkType: 'direct' | 'intent' | 'custom';
}

export function getProfileLinkProps(user: UserProfile): ProfileLinkProps {
  const url = generateProfileUrl(user);
  
  return {
    href: url,
    isExternal: true,
    hasUsername: !!user.username,
    linkType: user.user_link ? 'custom' : user.username ? 'direct' : 'intent'
  };
} 
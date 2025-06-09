# Profile Links Guide

This guide explains how to generate "go to profile" links using your existing Following and Followers data.

## Overview

The profile link system automatically generates Twitter profile URLs using a smart fallback strategy:

1. **Priority 1**: Use existing `user_link` if available
2. **Priority 2**: Generate `twitter.com/username` if username exists  
3. **Priority 3**: Fall back to Twitter intent URL with user ID

## Components

### ProfileLink (Base Component)
```tsx
import { ProfileLink } from '../common/ProfileLink';

<ProfileLink 
  user={{
    id: "12345",
    username: "elonmusk", 
    user_link: "https://twitter.com/elonmusk"
  }}
/>
```

### ProfileLinkButton (Button Style)
```tsx
import { ProfileLinkButton } from '../common/ProfileLink';

<ProfileLinkButton user={user} />
```

### ProfileLinkMinimal (Username Only)
```tsx
import { ProfileLinkMinimal } from '../common/ProfileLink';

<ProfileLinkMinimal user={user} />
// Renders: @username or @12345678 (last 8 chars of ID)
```

### ProfileLinkWithOptions (Dropdown with Multiple Links)
```tsx
import { ProfileLinkWithOptions } from '../common/ProfileLink';

<ProfileLinkWithOptions user={user} />
// Shows primary link + dropdown with Twitter.com, X.com, and Intent options
```

## Utility Functions

### generateProfileUrl()
```typescript
import { generateProfileUrl } from '../utils/profileLinks';

const url = generateProfileUrl({
  id: "12345",
  username: "jack",
  user_link: null
});
// Returns: "https://twitter.com/jack"
```

### generateProfileLinkOptions()
```typescript
import { generateProfileLinkOptions } from '../utils/profileLinks';

const options = generateProfileLinkOptions(user);
// Returns: {
//   primary: "https://twitter.com/jack",
//   username: "https://twitter.com/jack", 
//   intent: "https://twitter.com/intent/user?user_id=12345",
//   x_domain: "https://x.com/jack"
// }
```

### batchGenerateProfileUrls()
```typescript
import { batchGenerateProfileUrls } from '../utils/profileLinks';

const users = [/* array of users */];
const urlMap = batchGenerateProfileUrls(users);
// Returns: Map<userId, profileUrl>
```

## Data Requirements

The profile link system works with minimal user data:

```typescript
interface UserProfile {
  id: string;                    // Required: Twitter user ID
  username?: string | null;      // Optional: Twitter username (@handle)
  user_link?: string | null;     // Optional: Custom profile URL
}
```

## Link Generation Examples

| Data Available | Generated Link |
|----------------|----------------|
| `user_link` only | Uses `user_link` directly |
| `username` only | `https://twitter.com/username` |
| `id` only | `https://twitter.com/intent/user?user_id=12345` |
| All fields | Uses `user_link` (highest priority) |

## Current Implementation

The Following and Followers lists already use `ProfileLinkWithOptions`:

```tsx
<ProfileLinkWithOptions 
  user={{
    id: user.id,
    username: user.username,
    user_link: user.user_link
  }}
  className="text-sm font-medium"
/>
```

This provides:
- Primary "View Profile" link
- Dropdown with alternative link options (Twitter.com, X.com, Intent)
- Automatic fallback handling
- Consistent styling

## Advanced Features

### Link Validation
```typescript
import { isValidProfileLink } from '../utils/profileLinks';

const isValid = isValidProfileLink("https://twitter.com/jack");
// Returns: true for twitter.com and x.com domains
```

### Username Extraction
```typescript
import { extractUsernameFromUrl } from '../utils/profileLinks';

const username = extractUsernameFromUrl("https://twitter.com/jack");
// Returns: "jack"
```

### Custom Styling
```tsx
<ProfileLink 
  user={user}
  variant="button"           // 'default' | 'button' | 'minimal'
  className="custom-styles"
  showMultipleOptions={true}
/>
```

## Testing

A demo component is available at `ProfileLinkDemo.tsx` showing all variants with different data scenarios:

- User with complete data (username + user_link)
- User with username only
- User with custom link only  
- User with ID only

## Integration Notes

- All profile links open in new tabs (`target="_blank"`)
- Links include `rel="noopener noreferrer"` for security
- Hover states and accessibility attributes included
- Compatible with existing Following/Followers data structure
- No API calls required - works with cached data

## Future Enhancements

Potential improvements:
- Link preview on hover
- Analytics tracking for link clicks
- Bulk profile link validation
- Integration with profile enrichment system
- Custom domain support (e.g., company Twitter accounts) 
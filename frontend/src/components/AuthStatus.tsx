import { Card, Text, Group, Badge, Button, Stack, Progress } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { useEffect, useState } from 'react';

interface RateLimitInfo {
  is_rate_limited: boolean;
  reset_time: string | null;
  wait_seconds: number | null;
  endpoint: string | null;
}

interface AuthStatus {
  is_authenticated: boolean;
  username: string | null;
  error: string | null;
  can_fetch_data: boolean;
  test_tweet_count: number | null;
  rate_limit: RateLimitInfo | null;
  auth_steps: string[];
  current_step: string | null;
}

async function fetchAuthStatus() {
  const { data } = await axios.get<AuthStatus>('http://localhost:8000/api/test-auth');
  return data;
}

export function AuthStatusComponent() {
  const [countdown, setCountdown] = useState<number | null>(null);
  const { data: status, isLoading, error, refetch } = useQuery({
    queryKey: ['auth-status'],
    queryFn: fetchAuthStatus,
    retry: false,
    // Increase stale time to 5 minutes to prevent unnecessary refetches
    staleTime: 5 * 60 * 1000,
    // Only refetch on window focus if we're not rate limited
    refetchOnWindowFocus: (query) => {
      const data = query.state.data;
      return !data?.rate_limit?.is_rate_limited;
    },
    // Remove automatic refetch interval
    refetchInterval: false,
  });

  // Handle countdown for rate limit
  useEffect(() => {
    if (!status?.rate_limit?.wait_seconds) {
      setCountdown(null);
      return;
    }

    setCountdown(status.rate_limit.wait_seconds);
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev === null || prev <= 0) {
          clearInterval(timer);
          refetch();
          return null;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [status?.rate_limit?.wait_seconds, refetch]);

  if (isLoading) {
    return (
      <Card withBorder padding="md">
        <Stack gap="xs">
          <Text>Checking authentication status...</Text>
          <Progress size="sm" animated value={100} />
        </Stack>
      </Card>
    );
  }

  if (error) {
    return (
      <Card withBorder padding="md" style={{ borderColor: 'red' }}>
        <Stack gap="xs">
          <Text c="red" fw={500}>Failed to check authentication status</Text>
          <Text size="sm" c="dimmed">The backend server might not be running or is unreachable.</Text>
          <Button onClick={() => refetch()} variant="light" size="sm">
            Retry
          </Button>
        </Stack>
      </Card>
    );
  }

  if (!status) {
    return null;
  }

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  return (
    <Card withBorder padding="md" style={{ 
      borderColor: status.is_authenticated && status.can_fetch_data && !status.rate_limit?.is_rate_limited ? 'green' : 'red' 
    }}>
      <Stack gap="xs">
        <Group justify="space-between">
          <Text fw={500}>Twitter API Status</Text>
          <Group gap="xs">
            <Badge 
              color={status.is_authenticated ? 'green' : 'red'}
            >
              {status.is_authenticated ? 'Authenticated' : 'Not Authenticated'}
            </Badge>
            {status.can_fetch_data && !status.rate_limit?.is_rate_limited && (
              <Badge color="green">Can Fetch Data</Badge>
            )}
            {status.rate_limit?.is_rate_limited && (
              <Badge color="yellow">Rate Limited</Badge>
            )}
          </Group>
        </Group>

        {status.current_step && (
          <Text size="sm" c="dimmed" style={{ fontStyle: 'italic' }}>
            Current step: {status.current_step}
          </Text>
        )}

        {status.auth_steps.length > 0 && (
          <Stack gap="xs">
            <Text size="sm" fw={500}>Authentication Steps:</Text>
            {status.auth_steps.map((step, index) => (
              <Group key={index} gap="xs">
                <Badge size="sm" color="green" variant="light">✓</Badge>
                <Text size="sm">{step}</Text>
              </Group>
            ))}
          </Stack>
        )}

        {status.username && (
          <Text size="sm">Connected as: @{status.username}</Text>
        )}

        {status.test_tweet_count !== null && !status.rate_limit?.is_rate_limited && (
          <Text size="sm">Test tweet fetch: {status.test_tweet_count} tweets found</Text>
        )}

        {status.rate_limit?.is_rate_limited && (
          <Stack gap="xs">
            <Text size="sm" c="yellow" fw={500}>
              Rate limited on {status.rate_limit.endpoint}
            </Text>
            {countdown !== null && (
              <>
                <Text size="sm">Reset in: {formatTime(countdown)}</Text>
                <Progress 
                  value={(countdown / (status.rate_limit.wait_seconds || 1)) * 100} 
                  color="yellow"
                  size="sm"
                />
              </>
            )}
          </Stack>
        )}

        {status.error && !status.rate_limit?.is_rate_limited && (
          <Text size="sm" c="red">{status.error}</Text>
        )}

        <Button 
          onClick={() => refetch()} 
          variant="light" 
          size="sm"
          disabled={status.rate_limit?.is_rate_limited}
        >
          {status.rate_limit?.is_rate_limited ? 'Waiting for rate limit...' : 'Refresh Status'}
        </Button>
      </Stack>
    </Card>
  );
} 
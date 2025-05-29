import { Card, Text, Group, Button, Stack } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

interface Tweet {
  id: string;
  text: string;
  created_at: string;
  engagement_count: number;
}

async function fetchTweets() {
  const { data } = await axios.get<Tweet[]>('http://localhost:8000/api/tweets/zero-engagement');
  return data;
}

interface TweetListProps {
  isActive: boolean;
}

export function TweetList({ isActive }: TweetListProps) {
  const { data: tweets, isLoading, error, refetch } = useQuery({
    queryKey: ['tweets'],
    queryFn: fetchTweets,
    // Only fetch when the tab is active
    enabled: isActive,
    // Cache for 5 minutes
    staleTime: 5 * 60 * 1000,
    // Don't refetch automatically
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

  if (!isActive) return null;
  if (isLoading) return <Text>Loading tweets...</Text>;
  if (error) return <Text c="red">Error loading tweets</Text>;
  if (!tweets?.length) return <Text>No tweets with zero engagement found</Text>;

  return (
    <Stack gap="md">
      <Group justify="flex-end">
        <Button variant="light" size="sm" onClick={() => refetch()}>
          Refresh Tweets
        </Button>
      </Group>
      {tweets.map((tweet) => (
        <Card key={tweet.id} withBorder padding="md">
          <Stack gap="xs">
            <Text>{tweet.text}</Text>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">
                Posted on {new Date(tweet.created_at).toLocaleDateString()}
              </Text>
              <Button variant="light" color="red" size="sm">
                Delete Tweet
              </Button>
            </Group>
          </Stack>
        </Card>
      ))}
    </Stack>
  );
} 
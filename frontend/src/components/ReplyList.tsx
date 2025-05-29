import { Card, Text, Group, Button, Stack } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

interface Reply {
  id: string;
  text: string;
  created_at: string;
  engagement_count: number;
  in_reply_to: string;
}

async function fetchReplies() {
  const { data } = await axios.get<Reply[]>('http://localhost:8000/api/replies/zero-engagement');
  return data;
}

interface ReplyListProps {
  isActive: boolean;
}

export function ReplyList({ isActive }: ReplyListProps) {
  const { data: replies, isLoading, error, refetch } = useQuery({
    queryKey: ['replies'],
    queryFn: fetchReplies,
    // Only fetch when the tab is active
    enabled: isActive,
    // Cache for 5 minutes
    staleTime: 5 * 60 * 1000,
    // Don't refetch automatically
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

  if (!isActive) return null;
  if (isLoading) return <Text>Loading replies...</Text>;
  if (error) return <Text c="red">Error loading replies</Text>;
  if (!replies?.length) return <Text>No replies with zero engagement found</Text>;

  return (
    <Stack gap="md">
      <Group justify="flex-end">
        <Button variant="light" size="sm" onClick={() => refetch()}>
          Refresh Replies
        </Button>
      </Group>
      {replies.map((reply) => (
        <Card key={reply.id} withBorder padding="md">
          <Stack gap="xs">
            <Text>{reply.text}</Text>
            <Group justify="space-between">
              <Stack gap={0}>
                <Text size="sm" c="dimmed">
                  Posted on {new Date(reply.created_at).toLocaleDateString()}
                </Text>
                <Text size="sm" c="dimmed">
                  In reply to: {reply.in_reply_to}
                </Text>
              </Stack>
              <Button variant="light" color="red" size="sm">
                Delete Reply
              </Button>
            </Group>
          </Stack>
        </Card>
      ))}
    </Stack>
  );
} 
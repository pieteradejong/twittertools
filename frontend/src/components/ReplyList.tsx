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

export function ReplyList() {
  const { data: replies, isLoading, error } = useQuery({
    queryKey: ['replies'],
    queryFn: fetchReplies,
  });

  if (isLoading) return <Text>Loading replies...</Text>;
  if (error) return <Text c="red">Error loading replies</Text>;
  if (!replies?.length) return <Text>No replies with zero engagement found</Text>;

  return (
    <Stack gap="md">
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
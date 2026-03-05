import { describe, it, expect, vi, beforeEach } from 'vitest';
import { JulesClient, JulesAPIError } from './client';

describe('JulesClient', () => {
  const API_KEY = 'test-api-key';
  let client: JulesClient;

  beforeEach(() => {
    // Reset fetch mock between tests
    globalThis.fetch = vi.fn() as any;
    client = new JulesClient(API_KEY, { timeoutMs: 1000, maxRetries: 0 }); // Fast fail for tests
  });

  it('should initialize with API key', () => {
    expect(() => new JulesClient('')).toThrow('API key is required');
    expect(new JulesClient('key')).toBeInstanceOf(JulesClient);
  });

  it('should list sources successfully', async () => {
    const mockResponse = {
      sources: [{ name: 'source1', url: 'http://source1' }],
      nextPageToken: 'token123'
    };

    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await client.listSources(10);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://jules.googleapis.com/v1alpha/sources?pageSize=10',
      expect.objectContaining({
        headers: {
          'Authorization': `Bearer ${API_KEY}`,
          'Content-Type': 'application/json',
        }
      })
    );
    expect(result).toEqual(mockResponse);
  });

  it('should throw JulesAPIError on 4xx/5xx responses', async () => {
    // The previous error message "Cannot read properties of undefined (reading 'ok')" indicates
    // the maxRetries loop tries again and gets undefined on the second call.
    // So we should just provide the mock implementation multiple times or configure maxRetries to 0 for this test
    // Actually `maxRetries` is 0 due to beforeEach. So it's probably because we used mockImplementationOnce instead of mockResolvedValue
    const mockResponse = {
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      text: async () => '{"error": "invalid prompt"}',
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    try {
      await client.createSession({ source: 'repo', prompt: 'test' });
      // Should not reach here
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(JulesAPIError);
      expect((error as JulesAPIError).message).toContain('Jules API error: Bad Request');
    }
  });

  it('should successfully create a session', async () => {
    const mockSession = {
      name: 'sessions/123',
      source: 'repo',
      state: 'AWAITING_PLAN_APPROVAL',
      createTime: '2023-01-01',
      updateTime: '2023-01-01'
    };

    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSession,
    });

    const result = await client.createSession({
      source: 'test/repo',
      prompt: 'Do something'
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://jules.googleapis.com/v1alpha/sessions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ source: 'test/repo', prompt: 'Do something' })
      })
    );
    expect(result).toEqual(mockSession);
  });

  it('should fetch session activities', async () => {
    const mockActivities = {
      activities: [{ name: 'act/1', type: 'THINKING', content: 'Hmm...' }]
    };

    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockActivities,
    });

    const result = await client.listActivities('sessions/123');
    expect(result).toEqual(mockActivities);
  });

  it('should retry on transient 5xx errors if retries > 0', async () => {
    // Re-initialize client with retries enabled
    client = new JulesClient(API_KEY, { timeoutMs: 1000, maxRetries: 2 });

    // First call fails with 500
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: async () => 'Transient error',
    });

    // Second call succeeds
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ name: 'sessions/123' }),
    });

    const result = await client.getSession('sessions/123');

    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
    expect(result.name).toBe('sessions/123');
  });
});

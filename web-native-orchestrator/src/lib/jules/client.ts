/**
 * Activity Type extracted from jules-api.ts
 */
export interface Activity {
  name: string;
  session: string;
  createTime: string;
  type: string;
  content: string;
}

export interface ListActivitiesResponse {
  activities: Activity[];
  nextPageToken?: string;
}

export interface SendMessageRequest {
  prompt: string;
}

export interface CreateSessionRequest {
  source: string;
  prompt: string;
}

export interface Session {
  name: string;
  source: string;
  state: string;
  createTime: string;
  updateTime: string;
}

export interface ListSessionsResponse {
  sessions: Session[];
  nextPageToken?: string;
}

export interface Source {
  name: string;
  url: string;
}

export interface ListSourcesResponse {
  sources: Source[];
  nextPageToken?: string;
}

/**
 * Jules API Error
 */
export class JulesAPIError extends Error {
  public statusCode?: number;
  public response?: unknown;

  constructor(
    message: string,
    statusCode?: number,
    response?: unknown
  ) {
    super(message);
    this.name = 'JulesAPIError';
    this.statusCode = statusCode;
    this.response = response;
  }
}

/**
 * Client for interacting with the Google Jules REST API directly from the browser.
 */
export class JulesClient {
  private readonly baseURL = 'https://jules.googleapis.com/v1alpha';
  private readonly apiKey: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;

  constructor(apiKey: string, options: { timeoutMs?: number; maxRetries?: number } = {}) {
    if (!apiKey) {
      throw new Error('API key is required for JulesClient');
    }
    this.apiKey = apiKey;
    this.timeoutMs = options.timeoutMs || 15000;
    this.maxRetries = options.maxRetries || 2;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const headers = {
      'x-goog-api-key': this.apiKey,
      'Content-Type': 'application/json',
      ...options.headers,
    };

    let attempt = 0;
    let lastError: unknown;

    while (attempt <= this.maxRetries) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);
      try {
        const response = await fetch(url, {
          ...options,
          headers,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          const errorBody = await response.text();
          if (response.status >= 500 && attempt < this.maxRetries) {
            attempt++;
            lastError = new JulesAPIError(`Jules API error: ${response.statusText}`, response.status, errorBody);
            continue;
          }
          throw new JulesAPIError(`Jules API error: ${response.statusText}`, response.status, errorBody);
        }

        return (await response.json()) as T;
      } catch (error) {
        clearTimeout(timeoutId);
        const isAbort = error instanceof Error && error.name === 'AbortError';
        if ((isAbort || error instanceof Error) && attempt < this.maxRetries) {
          attempt++;
          lastError = error;
          continue;
        }
        if (error instanceof JulesAPIError) {
          throw error;
        }
        throw new JulesAPIError(`Network error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    }

    throw new JulesAPIError(
      `Network error after ${this.maxRetries + 1} attempts: ${
        lastError instanceof Error ? lastError.message : 'Unknown error'
      }`
    );
  }

  async listSources(pageSize = 100): Promise<ListSourcesResponse> {
    return this.request<ListSourcesResponse>(`/sources?pageSize=${pageSize}`);
  }

  async getSource(sourceName: string): Promise<Source> {
    return this.request<Source>(`/${sourceName}`);
  }

  async createSession(request: CreateSessionRequest): Promise<Session> {
    return this.request<Session>('/sessions', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async listSessions(pageSize = 20): Promise<ListSessionsResponse> {
    return this.request<ListSessionsResponse>(`/sessions?pageSize=${pageSize}`);
  }

  async getSession(sessionId: string): Promise<Session> {
    return this.request<Session>(`/sessions/${sessionId}`);
  }

  async approvePlan(sessionId: string): Promise<Session> {
    return this.request<Session>(`/sessions/${sessionId}:approvePlan`, {
      method: 'POST',
      body: '{}',
    });
  }

  async sendMessage(sessionId: string, request: SendMessageRequest): Promise<Session> {
    return this.request<Session>(`/sessions/${sessionId}:sendMessage`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async listActivities(sessionId: string, pageSize = 50): Promise<ListActivitiesResponse> {
    return this.request<ListActivitiesResponse>(`/sessions/${sessionId}/activities?pageSize=${pageSize}`);
  }
}

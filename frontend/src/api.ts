import type { UserMe, Team, TeamMember, WorkItem, WorkItemListResponse, ActivityLog } from './types';

const API_BASE = 'http://localhost:8000';

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      sessionStorage.setItem('newtonite_token', token);
    } else {
      sessionStorage.removeItem('newtonite_token');
    }
  }

  getToken(): string | null {
    if (!this.token) {
      this.token = sessionStorage.getItem('newtonite_token');
    }
    return this.token;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = { detail: response.statusText };
      }

      const error: any = new Error(
        typeof errorData.detail === 'string'
          ? errorData.detail
          : errorData.detail?.message || 'API request failed'
      );
      error.status = response.status;
      error.data = errorData;
      throw error;
    }

    return response.json();
  }

  async login(email: string, password: string) {
    const data = await this.request<{ access_token: string; user: any }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  logout() {
    this.setToken(null);
  }

  async getMe(): Promise<UserMe> {
    return this.request<UserMe>('/auth/me');
  }

  async getTeams(): Promise<Team[]> {
    return this.request<Team[]>('/teams');
  }

  async getTeamMembers(teamId: string): Promise<TeamMember[]> {
    return this.request<TeamMember[]>(`/teams/${teamId}/members`);
  }

  async listItems(params: Record<string, any> = {}): Promise<WorkItemListResponse> {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        query.append(k, String(v));
      }
    });
    return this.request<WorkItemListResponse>(`/items?${query.toString()}`);
  }

  async getItem(id: string): Promise<WorkItem> {
    return this.request<WorkItem>(`/items/${id}`);
  }

  async createItem(payload: any, idempotencyKey?: string): Promise<WorkItem> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    return this.request<WorkItem>('/items', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
  }

  async updateItem(id: string, payload: any): Promise<WorkItem> {
    return this.request<WorkItem>(`/items/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async claimItem(id: string, version: number): Promise<WorkItem> {
    return this.request<WorkItem>(`/items/${id}/claim`, {
      method: 'POST',
      body: JSON.stringify({ version }),
    });
  }

  async transitionItem(id: string, status: string, version: number, comment?: string): Promise<WorkItem> {
    return this.request<WorkItem>(`/items/${id}/transition`, {
      method: 'POST',
      body: JSON.stringify({ status, version, comment }),
    });
  }

  async getItemActivity(id: string): Promise<ActivityLog[]> {
    return this.request<ActivityLog[]>(`/items/${id}/activity`);
  }
}

export const api = new ApiClient();

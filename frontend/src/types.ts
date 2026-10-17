export type TeamRole = 'VIEWER' | 'MEMBER' | 'LEAD' | 'ADMIN';
export type WorkItemType = 'INCIDENT' | 'CUSTOMER_ISSUE' | 'PAYMENT' | 'COMPLIANCE' | 'TASK';
export type WorkItemPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type WorkItemStatus = 'OPEN' | 'IN_PROGRESS' | 'AWAITING_APPROVAL' | 'RESOLVED' | 'CLOSED';

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: number;
}

export interface TeamMembership {
  team_id: string;
  team_name: string;
  team_slug: string;
  role: TeamRole;
}

export interface UserMe extends User {
  memberships: TeamMembership[];
}

export interface Team {
  id: string;
  name: string;
  slug: string;
  description?: string;
  my_role?: TeamRole;
}

export interface TeamMember {
  user_id: string;
  full_name: string;
  email: string;
  role: TeamRole;
}

export interface WorkItem {
  id: string;
  title: string;
  description: string;
  type: WorkItemType;
  priority: WorkItemPriority;
  status: WorkItemStatus;
  team_id: string;
  team_name?: string;
  creator_id: string;
  creator_name?: string;
  assignee_id?: string;
  assignee_name?: string;
  due_date?: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface WorkItemListResponse {
  items: WorkItem[];
  total: number;
  page: number;
  limit: number;
  has_next: boolean;
}

export interface ActivityLog {
  id: string;
  work_item_id: string;
  actor_id: string;
  actor_name?: string;
  action: string;
  before_state?: Record<string, any>;
  after_state?: Record<string, any>;
  comment?: string;
  created_at: string;
}

import React, { useState, useEffect } from 'react';
import { api } from './api';
import type { UserMe, Team, WorkItem } from './types';

import { Login } from './components/Login';
import { CreateItemModal } from './components/CreateItemModal';
import { ItemDetailModal } from './components/ItemDetailModal';

export const App: React.FC = () => {
  const [user, setUser] = useState<UserMe | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [items, setItems] = useState<WorkItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [dashboardTab, setDashboardTab] = useState<'all' | 'assigned_to_me' | 'urgent_unassigned' | 'awaiting_approval'>('all');
  
  const [loading, setLoading] = useState(false);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const checkAuth = async () => {
    if (!api.getToken()) return;
    try {
      const me = await api.getMe();
      setUser(me);
      const teamList = await api.getTeams();
      setTeams(teamList);
      if (teamList.length > 0 && !selectedTeam) {
        setSelectedTeam(teamList[0].id);
      }
    } catch {
      api.logout();
      setUser(null);
    }
  };

  const loadItems = async () => {
    if (!user) return;
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        limit: 10,
        team_id: selectedTeam || undefined,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        search: search || undefined,
      };

      if (dashboardTab === 'assigned_to_me') {
        params.assigned_to_me = true;
      } else if (dashboardTab === 'urgent_unassigned') {
        params.unassigned_urgent = true;
      } else if (dashboardTab === 'awaiting_approval') {
        params.awaiting_my_approval = true;
      }

      const res = await api.listItems(params);
      setItems(res.items);
      setTotalItems(res.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (user) {
      loadItems();
    }
  }, [user, selectedTeam, statusFilter, priorityFilter, search, dashboardTab, page]);

  if (!user) {
    return <Login onSuccess={checkAuth} />;
  }

  const currentTeamObj = teams.find((t) => t.id === selectedTeam);
  const myCurrentRole = currentTeamObj?.my_role;
  const isViewer = myCurrentRole === 'VIEWER';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <span className="text-xl font-black text-indigo-400 tracking-wider">NEWTONITE</span>
          <span className="text-xs bg-indigo-950 text-indigo-300 border border-indigo-800 px-2 py-0.5 rounded font-mono">
            OPERATIONS DESK
          </span>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-sm font-bold text-white">{user.full_name}</div>
            <div className="text-xs text-slate-400">{user.email}</div>
          </div>
          <button
            onClick={() => {
              api.logout();
              setUser(null);
            }}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs border border-slate-700"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Controls Bar */}
        <div className="flex flex-wrap justify-between items-center gap-4 bg-slate-900 p-4 rounded-xl border border-slate-800">
          <div className="flex items-center gap-3">
            <label className="text-xs font-semibold text-slate-400 uppercase">Team:</label>
            <select
              value={selectedTeam}
              onChange={(e) => {
                setSelectedTeam(e.target.value);
                setPage(1);
              }}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white"
            >
              {teams.map((t) => (
                <option key={t.id} value={t.id}>{t.name} ({t.my_role})</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            {!isViewer && (
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm rounded-lg transition shadow-md"
              >
                + New Work Item
              </button>
            )}
          </div>
        </div>

        {/* Dashboard Tabs */}
        <div className="flex gap-2 border-b border-slate-800 pb-2">
          <button
            onClick={() => { setDashboardTab('all'); setPage(1); }}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition ${
              dashboardTab === 'all' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            All Items
          </button>
          <button
            onClick={() => { setDashboardTab('assigned_to_me'); setPage(1); }}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition ${
              dashboardTab === 'assigned_to_me' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Assigned to Me
          </button>
          <button
            onClick={() => { setDashboardTab('urgent_unassigned'); setPage(1); }}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition ${
              dashboardTab === 'urgent_unassigned' ? 'bg-amber-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Unassigned Urgent Items
          </button>
          <button
            onClick={() => { setDashboardTab('awaiting_approval'); setPage(1); }}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition ${
              dashboardTab === 'awaiting_approval' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Awaiting My Approval
          </button>
        </div>

        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search items by title or description..."
            className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
          />

          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-300"
          >
            <option value="">All Statuses</option>
            <option value="OPEN">Open</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="AWAITING_APPROVAL">Awaiting Approval</option>
            <option value="RESOLVED">Resolved</option>
            <option value="CLOSED">Closed</option>
          </select>

          <select
            value={priorityFilter}
            onChange={(e) => { setPriorityFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-300"
          >
            <option value="">All Priorities</option>
            <option value="LOW">Low</option>
            <option value="MEDIUM">Medium</option>
            <option value="HIGH">High</option>
            <option value="CRITICAL">Critical</option>
          </select>
        </div>

        {/* Item List / Table */}
        <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden shadow-xl">
          {loading ? (
            <div className="p-8 text-center text-slate-400">Loading work items...</div>
          ) : items.length === 0 ? (
            <div className="p-12 text-center text-slate-500">
              No work items match the selected filter criteria.
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-800/60 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  <th className="py-3 px-4">Title</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Assignee</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-sm">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-white">{item.title}</div>
                      <div className="text-xs text-slate-400 line-clamp-1">{item.description}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-xs bg-slate-800 px-2 py-0.5 rounded text-slate-300">
                        {item.type}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                        item.priority === 'CRITICAL' ? 'bg-red-950 text-red-300 border border-red-800' :
                        item.priority === 'HIGH' ? 'bg-orange-950 text-orange-300 border border-orange-800' :
                        'bg-slate-800 text-slate-300'
                      }`}>
                        {item.priority}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-xs bg-indigo-950 text-indigo-300 border border-indigo-800 px-2 py-0.5 rounded">
                        {item.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-300">
                      {item.assignee_name || <span className="text-amber-400 italic">Unassigned</span>}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedItemId(item.id)}
                        className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded border border-slate-700 transition"
                      >
                        Inspect & Act
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Pagination bar */}
          <div className="px-4 py-3 bg-slate-900 border-t border-slate-800 flex justify-between items-center text-xs text-slate-400">
            <div>Total Items: {totalItems}</div>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1 bg-slate-800 text-slate-200 rounded disabled:opacity-40"
              >
                Previous
              </button>
              <span className="px-2 py-1 font-mono">Page {page}</span>
              <button
                disabled={page * 10 >= totalItems}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 bg-slate-800 text-slate-200 rounded disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Modals */}
      {showCreateModal && (
        <CreateItemModal
          teams={teams}
          onClose={() => setShowCreateModal(false)}
          onCreated={loadItems}
        />
      )}

      {selectedItemId && (
        <ItemDetailModal
          itemId={selectedItemId}
          currentUser={user}
          myRole={myCurrentRole}
          onClose={() => setSelectedItemId(null)}
          onItemUpdated={loadItems}
        />
      )}
    </div>
  );
};

export default App;

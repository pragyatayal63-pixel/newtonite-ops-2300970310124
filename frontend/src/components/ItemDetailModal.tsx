import React, { useState, useEffect } from 'react';
import { api } from '../api';
import type { WorkItem, ActivityLog, UserMe, TeamRole } from '../types';

interface ItemDetailModalProps {
  itemId: string;
  currentUser?: UserMe;
  myRole?: TeamRole;
  onClose: () => void;
  onItemUpdated: () => void;
}


export const ItemDetailModal: React.FC<ItemDetailModalProps> = ({
  itemId,
  myRole,
  onClose,
  onItemUpdated,
}) => {

  const [item, setItem] = useState<WorkItem | null>(null);
  const [activities, setActivities] = useState<ActivityLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<boolean>(false);
  const [comment, setComment] = useState('');

  const loadItem = async () => {
    setLoading(true);
    setError(null);
    setConflict(false);
    try {
      const [itemData, actData] = await Promise.all([
        api.getItem(itemId),
        api.getItemActivity(itemId),
      ]);
      setItem(itemData);
      setActivities(actData);
    } catch (err: any) {
      setError(err.message || 'Failed to load work item details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItem();
  }, [itemId]);

  const handleClaim = async () => {
    if (!item) return;
    setActionLoading(true);
    setError(null);
    try {
      await api.claimItem(item.id, item.version);
      await loadItem();
      onItemUpdated();
    } catch (err: any) {
      if (err.status === 409) {
        setConflict(true);
      }
      setError(err.message || 'Claim failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleTransition = async (targetStatus: string) => {
    if (!item) return;
    setActionLoading(true);
    setError(null);
    try {
      await api.transitionItem(item.id, targetStatus, item.version, comment || undefined);
      setComment('');
      await loadItem();
      onItemUpdated();
    } catch (err: any) {
      if (err.status === 409) {
        setConflict(true);
      }
      setError(err.message || 'Transition failed');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
        <div className="bg-slate-800 p-6 rounded-xl text-white">Loading work item...</div>
      </div>
    );
  }

  if (!item) {
    return null;
  }

  const isViewer = myRole === 'VIEWER';
  const isLead = myRole === 'LEAD' || myRole === 'ADMIN';

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-slate-800 border border-slate-700 rounded-xl max-w-2xl w-full p-6 shadow-2xl max-h-[90vh] flex flex-col">
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-700 text-slate-300">
                {item.type}
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                item.priority === 'CRITICAL' ? 'bg-red-900/50 text-red-300 border border-red-700' :
                item.priority === 'HIGH' ? 'bg-orange-900/50 text-orange-300 border border-orange-700' :
                'bg-slate-700 text-slate-300'
              }`}>
                {item.priority}
              </span>
              <span className="px-2 py-0.5 rounded text-xs font-semibold bg-indigo-900/50 text-indigo-300 border border-indigo-700">
                {item.status}
              </span>
              <span className="text-xs text-slate-500 font-mono">v{item.version}</span>
            </div>
            <h2 className="text-xl font-bold text-white mt-2">{item.title}</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-lg">✕</button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-950/80 border border-red-500/50 rounded-lg text-red-200 text-sm flex justify-between items-center">
            <span>{error}</span>
            {conflict && (
              <button
                onClick={loadItem}
                className="ml-4 px-2.5 py-1 bg-red-800 hover:bg-red-700 text-xs font-bold rounded"
              >
                Reload Latest State
              </button>
            )}
          </div>
        )}

        <div className="flex-1 overflow-y-auto space-y-6 pr-2">
          {/* Metadata */}
          <div className="grid grid-cols-2 gap-4 bg-slate-900/50 p-4 rounded-lg border border-slate-700 text-sm">
            <div>
              <span className="text-slate-400 block text-xs">Team</span>
              <span className="text-slate-200 font-medium">{item.team_name}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-xs">Assignee</span>
              <span className="text-slate-200 font-medium">{item.assignee_name || 'Unassigned'}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-xs">Creator</span>
              <span className="text-slate-200">{item.creator_name}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-xs">Created At</span>
              <span className="text-slate-200">{new Date(item.created_at).toLocaleString()}</span>
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Description</h3>
            <p className="text-slate-200 bg-slate-900/30 p-3 rounded-lg border border-slate-800 text-sm whitespace-pre-wrap">
              {item.description}
            </p>
          </div>

          {/* Workflow & Actions */}
          {!isViewer && (
            <div className="bg-slate-900/40 p-4 rounded-lg border border-slate-700/80">
              <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">Workflow Actions</h3>
              
              <div className="flex flex-wrap gap-2 items-center">
                {/* Claim action */}
                {!item.assignee_id && item.status === 'OPEN' && (
                  <button
                    onClick={handleClaim}
                    disabled={actionLoading}
                    className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-sm font-medium transition disabled:opacity-50"
                  >
                    Claim Item (Atomic)
                  </button>
                )}

                {/* Open -> In Progress */}
                {item.status === 'OPEN' && (
                  <button
                    onClick={() => handleTransition('IN_PROGRESS')}
                    disabled={actionLoading}
                    className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm font-medium transition disabled:opacity-50"
                  >
                    Start Progress
                  </button>
                )}

                {/* In Progress -> Awaiting Approval */}
                {item.status === 'IN_PROGRESS' && (
                  <button
                    onClick={() => handleTransition('AWAITING_APPROVAL')}
                    disabled={actionLoading}
                    className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded text-sm font-medium transition disabled:opacity-50"
                  >
                    Request Lead Approval
                  </button>
                )}

                {/* Awaiting Approval -> Resolved (Lead only!) */}
                {item.status === 'AWAITING_APPROVAL' && isLead && (
                  <button
                    onClick={() => handleTransition('RESOLVED')}
                    disabled={actionLoading}
                    className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-sm font-medium transition disabled:opacity-50"
                  >
                    Approve (Resolve)
                  </button>
                )}

                {/* Resolved -> Closed */}
                {item.status === 'RESOLVED' && (
                  <button
                    onClick={() => handleTransition('CLOSED')}
                    disabled={actionLoading}
                    className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded text-sm font-medium transition disabled:opacity-50"
                  >
                    Close Work Item
                  </button>
                )}
              </div>

              {item.status === 'AWAITING_APPROVAL' && !isLead && (
                <p className="text-xs text-amber-400 mt-2">
                  Approval requires a team Lead. You are currently logged in as a Member/Viewer.
                </p>
              )}
            </div>
          )}

          {/* Activity Log */}
          <div>
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Activity & Audit History</h3>
            <div className="space-y-3">
              {activities.length === 0 ? (
                <p className="text-slate-500 text-xs">No activity recorded yet.</p>
              ) : (
                activities.map((act) => (
                  <div key={act.id} className="text-xs bg-slate-900/60 p-3 rounded border border-slate-800">
                    <div className="flex justify-between text-slate-400">
                      <span className="font-semibold text-slate-200">{act.actor_name || 'System'}</span>
                      <span>{new Date(act.created_at).toLocaleString()}</span>
                    </div>
                    <div className="mt-1 font-medium text-indigo-400">{act.action}</div>
                    {act.comment && (
                      <div className="mt-1 text-slate-300 italic">"{act.comment}"</div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import { api } from '../api';

interface LoginProps {
  onSuccess: () => void;
}

export const Login: React.FC<LoginProps> = ({ onSuccess }) => {
  const [email, setEmail] = useState('lead@newtonite.io');
  const [password, setPassword] = useState('Password123!');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.login(email, password);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const setDemoRole = (userEmail: string) => {
    setEmail(userEmail);
    setPassword('Password123!');
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-slate-800 rounded-xl shadow-2xl p-8 border border-slate-700">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Newtonite</h1>
          <p className="text-slate-400 text-sm mt-1">Operations Under Pressure</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-950/80 border border-red-500/50 rounded-lg text-red-200 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-indigo-500"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-indigo-500"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition disabled:opacity-50"
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-slate-700">
          <p className="text-xs text-slate-400 font-semibold uppercase mb-3">Quick Demo Logins (Password: Password123!)</p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <button
              onClick={() => setDemoRole('lead@newtonite.io')}
              className="p-2 bg-slate-700/50 hover:bg-slate-700 text-left rounded border border-slate-600 text-slate-200"
            >
              <div className="font-bold text-indigo-400">Alice (Lead)</div>
              <div className="text-[11px] text-slate-400">Ops Core Lead</div>
            </button>
            <button
              onClick={() => setDemoRole('member@newtonite.io')}
              className="p-2 bg-slate-700/50 hover:bg-slate-700 text-left rounded border border-slate-600 text-slate-200"
            >
              <div className="font-bold text-emerald-400">Bob (Member)</div>
              <div className="text-[11px] text-slate-400">Ops Core Member</div>
            </button>
            <button
              onClick={() => setDemoRole('viewer@newtonite.io')}
              className="p-2 bg-slate-700/50 hover:bg-slate-700 text-left rounded border border-slate-600 text-slate-200"
            >
              <div className="font-bold text-amber-400">Charlie (Viewer)</div>
              <div className="text-[11px] text-slate-400">Read-Only Ops</div>
            </button>
            <button
              onClick={() => setDemoRole('finlead@newtonite.io')}
              className="p-2 bg-slate-700/50 hover:bg-slate-700 text-left rounded border border-slate-600 text-slate-200"
            >
              <div className="font-bold text-purple-400">Diana (Fin Lead)</div>
              <div className="text-[11px] text-slate-400">Fin Compliance</div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

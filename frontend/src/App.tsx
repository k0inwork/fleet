import { useState, useEffect } from 'react';
import { Play, AlertCircle, CheckCircle, Clock, XCircle, RotateCcw } from 'lucide-react';

const API_BASE = '/api';

type TaskStatus = 'pending' | 'ready' | 'running' | 'completed' | 'failed' | 'conflicted' | 'waiting' | 'approved' | 'rejected' | 'retry';

interface Task {
  id: string;
  status: TaskStatus;
  instruction: string;
  session_id: string | null;
}

interface VM {
  session_id: string;
  branch: string;
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [vms, setVMs] = useState<VM[]>([]);
  const [selectedVM, setSelectedVM] = useState<string | null>(null);
  const [vmLogs, setVMLogs] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Configuration Form State
  const [userGoal, setUserGoal] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [julesApiKey, setJulesApiKey] = useState('');
  const [ghToken, setGhToken] = useState('');
  const [repoName, setRepoName] = useState('');

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/status`);
        if (res.ok) {
          const data = await res.json();
          setTasks(data.tasks);
          setIsRunning(data.status === 'running');
        }
      } catch (err) {
        console.error('Failed to fetch status:', err);
      }
    };

    const fetchVMs = async () => {
      try {
        const res = await fetch(`${API_BASE}/vms`);
        if (res.ok) {
          const data = await res.json();
          setVMs(data.vms);
        }
      } catch (err) {
        console.error('Failed to fetch VMs:', err);
      }
    };

    const interval = setInterval(() => {
      fetchStatus();
      fetchVMs();
    }, 3000);

    // Initial fetch
    fetchStatus();
    fetchVMs();

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!selectedVM) return;

    const fetchLogs = async () => {
      try {
        const res = await fetch(`${API_BASE}/vms/${selectedVM}/logs`);
        if (res.ok) {
          const data = await res.json();
          setVMLogs(data.logs);
        }
      } catch (err) {
        console.error('Failed to fetch VM logs:', err);
      }
    };

    const logInterval = setInterval(fetchLogs, 3000);
    fetchLogs();

    return () => clearInterval(logInterval);
  }, [selectedVM]);

  const handleStart = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_goal: userGoal,
          gemini_api_key: apiKey,
          jules_api_key: julesApiKey || apiKey,
          github_token: ghToken,
          repo_full_name: repoName,
          repo_path: '.'
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to start');
      }
      setIsRunning(true);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleHILDecision = async (taskId: string, decision: 'approve' | 'reject' | 'retry') => {
    try {
      await fetch(`${API_BASE}/hil/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, decision })
      });
      // Force immediate refresh (it'll also catch up in the interval)
    } catch (err) {
      console.error('Failed HIL decision:', err);
    }
  };

  const StatusIcon = ({ status }: { status: TaskStatus }) => {
    switch (status) {
      case 'completed': case 'approved': return <CheckCircle className="text-green-500 w-5 h-5" />;
      case 'running': return <Play className="text-blue-500 w-5 h-5" />;
      case 'waiting': return <AlertCircle className="text-yellow-500 w-5 h-5 animate-pulse" />;
      case 'failed': case 'rejected': case 'conflicted': return <XCircle className="text-red-500 w-5 h-5" />;
      case 'retry': return <RotateCcw className="text-orange-500 w-5 h-5" />;
      default: return <Clock className="text-gray-400 w-5 h-5" />;
    }
  };

  const waitingTasks = tasks.filter(t => t.status === 'waiting');

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Jules Workflow Orchestrator</h1>
        <p className="text-gray-600">AI-driven development workflow management</p>
      </header>

      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-8">
          <p>{error}</p>
        </div>
      )}

      {/* Setup Form */}
      {!isRunning && tasks.length === 0 && (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 mb-8 max-w-2xl">
          <h2 className="text-xl font-semibold mb-4">Start New Workflow</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">User Goal</label>
              <textarea
                className="w-full border-gray-300 rounded-md shadow-sm p-2 border focus:ring-blue-500 focus:border-blue-500"
                rows={3}
                value={userGoal}
                onChange={e => setUserGoal(e.target.value)}
                placeholder="e.g., Build a login page with React..."
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Gemini API Key</label>
                <input
                  type="password"
                  className="w-full border-gray-300 rounded-md shadow-sm p-2 border"
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Jules API Key (optional)</label>
                <input
                  type="password"
                  placeholder="Defaults to Gemini key"
                  className="w-full border-gray-300 rounded-md shadow-sm p-2 border"
                  value={julesApiKey}
                  onChange={e => setJulesApiKey(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">GitHub Token</label>
                <input
                  type="password"
                  className="w-full border-gray-300 rounded-md shadow-sm p-2 border"
                  value={ghToken}
                  onChange={e => setGhToken(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Repository Name (owner/repo)</label>
                <input
                  type="text"
                  className="w-full border-gray-300 rounded-md shadow-sm p-2 border"
                  value={repoName}
                  onChange={e => setRepoName(e.target.value)}
                />
              </div>
            </div>
            <button
              onClick={handleStart}
              className="mt-4 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition"
            >
              Generate Graph & Start
            </button>
          </div>
        </div>
      )}

      {/* HIL Approvals */}
      {waitingTasks.length > 0 && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-8 rounded-r-lg shadow-sm">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <AlertCircle className="h-5 w-5 text-yellow-400" />
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-sm font-medium text-yellow-800">Action Required: Human-in-the-Loop</h3>
              <div className="mt-2 text-sm text-yellow-700">
                <p>The following task(s) require human approval before the workflow can proceed:</p>
                <ul className="mt-2 space-y-3">
                  {waitingTasks.map(task => (
                    <li key={task.id} className="bg-white p-3 rounded shadow-sm">
                      <p className="font-semibold">{task.id}</p>
                      <p className="text-gray-600 mb-3">{task.instruction}</p>
                      <div className="flex space-x-3">
                        <button onClick={() => handleHILDecision(task.id, 'approve')} className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700">Approve</button>
                        <button onClick={() => handleHILDecision(task.id, 'reject')} className="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700">Reject</button>
                        <button onClick={() => handleHILDecision(task.id, 'retry')} className="bg-orange-500 text-white px-3 py-1 rounded text-sm hover:bg-orange-600">Retry</button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Dashboard layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Task List */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-gray-800">Task Graph Status</h2>
            <span className={`px-2 py-1 text-xs rounded-full ${isRunning ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}`}>
              {isRunning ? 'Running' : 'Idle'}
            </span>
          </div>
          <ul className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
            {tasks.map(task => (
              <li key={task.id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <StatusIcon status={task.status} />
                    <div>
                      <p className="text-sm font-medium text-gray-900">{task.id}</p>
                      <p className="text-xs text-gray-500 truncate max-w-md">{task.instruction}</p>
                    </div>
                  </div>
                  <span className="text-xs font-mono text-gray-500 uppercase tracking-wider">{task.status}</span>
                </div>
              </li>
            ))}
            {tasks.length === 0 && (
              <li className="px-6 py-8 text-center text-gray-500 text-sm">No tasks available.</li>
            )}
          </ul>
        </div>

        {/* Jules VMs and Logs */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-800">Active Jules VMs</h2>
          </div>
          <div className="p-4 border-b border-gray-200">
            <label className="block text-sm font-medium text-gray-700 mb-2">Select Session to View Logs</label>
            <select
              className="block w-full border-gray-300 rounded-md shadow-sm p-2 border focus:ring-blue-500 focus:border-blue-500"
              value={selectedVM || ''}
              onChange={e => setSelectedVM(e.target.value)}
            >
              <option value="">-- Select VM Session --</option>
              {vms.map(vm => (
                <option key={vm.session_id} value={vm.session_id}>
                  {vm.session_id} (Branch: {vm.branch})
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 bg-gray-900 p-4 font-mono text-sm text-green-400 overflow-y-auto min-h-[400px]">
            {selectedVM ? (
              vmLogs.length > 0 ? (
                vmLogs.map((log, i) => <div key={i} className="mb-1">{log}</div>)
              ) : (
                <div className="text-gray-500 italic">No logs available for this session yet.</div>
              )
            ) : (
              <div className="text-gray-500 italic">Select a VM session to view its live logs.</div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { useJulesSession } from './lib/jules/hooks';
import { AGENTS_MD_BOOTSTRAP } from './lib/jules/prompts';
import { Play, Loader2, CheckCircle, XCircle, Send, Settings, Save, Github, AlertTriangle } from 'lucide-react';

function App() {
  const [apiKey, setApiKey] = useState<string>(() => localStorage.getItem('JULES_API_KEY') || '');
  const [source, setSource] = useState<string>(() => localStorage.getItem('JULES_SOURCE') || '');
  const [sessionId, setSessionId] = useState<string>(() => localStorage.getItem('JULES_SESSION_ID') || '');

  const [taskPrompt, setTaskPrompt] = useState('');
  const [isConfigOpen, setIsConfigOpen] = useState(!apiKey || !source);
  const [isCreatingSession, setIsCreatingSession] = useState(false);

  const {
    session,
    activities,
    status: pollingStatus,
    error: pollingError,
    approvePlan,
    sendMessage,
    getClient,
    refresh
  } = useJulesSession(apiKey, sessionId);

  // Auto-save to localStorage
  useEffect(() => {
    localStorage.setItem('JULES_API_KEY', apiKey);
  }, [apiKey]);

  useEffect(() => {
    localStorage.setItem('JULES_SOURCE', source);
  }, [source]);

  useEffect(() => {
    localStorage.setItem('JULES_SESSION_ID', sessionId);
  }, [sessionId]);

  const handleCreateSession = async () => {
    const client = getClient();
    if (!client || !source || !taskPrompt) return;

    setIsCreatingSession(true);
    try {
      // Inject the bootstrap script into the initial prompt
      const injectedPrompt = `${AGENTS_MD_BOOTSTRAP}\n\n### Task Description:\n${taskPrompt}`;

      const newSession = await client.createSession({
        source: source,
        prompt: injectedPrompt,
      });

      setSessionId(newSession.name); // Using 'name' as it's the full resource name/ID in Jules API
      setTaskPrompt('');
    } catch (error) {
      console.error("Failed to create session:", error);
      alert("Failed to create session. See console.");
    } finally {
      setIsCreatingSession(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskPrompt) return;

    try {
      await sendMessage(taskPrompt);
      setTaskPrompt('');
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  };

  // Extract PR links if Jules provides them in activities
  const prLinks = activities
    .map(a => a.content)
    .join(' ')
    .match(/https:\/\/github\.com\/[^/]+\/[^/]+\/pull\/\d+/g) || [];

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col text-slate-800">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 p-2 rounded-lg text-white">
            <Play size={20} />
          </div>
          <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">
            AI Cockpit Orchestrator
          </h1>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-sm px-3 py-1 rounded-full bg-slate-100 border border-slate-200 flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${pollingStatus === 'polling' ? 'bg-green-500 animate-pulse' : 'bg-slate-400'}`}></div>
            {pollingStatus === 'polling' ? 'Polling VM' : 'Idle'}
          </div>

          <button
            onClick={() => setIsConfigOpen(!isConfigOpen)}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <Settings size={20} className="text-gray-600" />
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-5xl w-full mx-auto p-6 flex flex-col gap-6">

        {/* Configuration Panel */}
        {isConfigOpen && (
          <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Settings size={18} /> Configuration
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Jules API Key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="AIzaSy..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Source (Repository)</label>
                <input
                  type="text"
                  value={source}
                  onChange={e => setSource(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="github/user/repo"
                />
              </div>
              <div className="md:col-span-2">
                <button
                  onClick={() => setIsConfigOpen(false)}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                  <Save size={16} /> Save & Close
                </button>
              </div>
            </div>
          </div>
        )}

        {/* New Session Creation (if no session active) */}
        {!sessionId && !isConfigOpen && (
          <div className="bg-white p-8 rounded-xl border border-gray-200 shadow-sm text-center flex flex-col items-center gap-4 max-w-2xl mx-auto w-full mt-10">
            <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center mb-2">
              <Play size={32} />
            </div>
            <h2 className="text-2xl font-bold">Start a new Jules Session</h2>
            <p className="text-gray-500 mb-4">
              Enter a task description below. Qwen-3.5 (Orchestrator Proxy) will inject the AGENTS.md bootstrap instructions and manage the headless Jules VM to complete the task.
            </p>

            <textarea
              value={taskPrompt}
              onChange={e => setTaskPrompt(e.target.value)}
              className="w-full h-32 px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              placeholder="E.g., Update the README to include WebLLM instructions, make sure tests pass..."
            />

            <button
              onClick={handleCreateSession}
              disabled={isCreatingSession || !taskPrompt || !apiKey || !source}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed w-full justify-center"
            >
              {isCreatingSession ? <Loader2 className="animate-spin" /> : <Play size={18} />}
              {isCreatingSession ? 'Starting Proxy VM...' : 'Dispatch Task to VM'}
            </button>
          </div>
        )}

        {/* Active Session View */}
        {sessionId && session && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* Left Column: VM State & HIL Controls */}
            <div className="lg:col-span-1 flex flex-col gap-6">

              <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">VM Status Overview</h3>

                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Session ID</p>
                    <p className="text-sm font-mono bg-gray-100 px-2 py-1 rounded border border-gray-200 truncate" title={session.name}>
                      {session.name.split('/').pop()}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-gray-500 mb-1">State</p>
                    <div className="flex items-center gap-2">
                      {session.state === 'COMPLETED' ? (
                        <CheckCircle size={18} className="text-green-500" />
                      ) : session.state === 'ERROR' ? (
                        <XCircle size={18} className="text-red-500" />
                      ) : session.state === 'AWAITING_PLAN_APPROVAL' ? (
                        <div className="w-4 h-4 bg-amber-500 rounded-full animate-pulse" />
                      ) : (
                        <Loader2 size={18} className="text-blue-500 animate-spin" />
                      )}
                      <span className="font-semibold text-sm">
                        {session.state}
                      </span>
                    </div>
                  </div>

                  {session.state === 'AWAITING_PLAN_APPROVAL' && (
                    <div className="pt-2 border-t border-gray-100 mt-2">
                      <p className="text-sm text-amber-600 mb-3 bg-amber-50 p-2 rounded border border-amber-200">
                        The VM has proposed a plan and is waiting for your approval.
                      </p>
                      <button
                        onClick={approvePlan}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-amber-500 text-white rounded-md hover:bg-amber-600 transition-colors font-medium text-sm"
                      >
                        <CheckCircle size={16} /> Approve Plan
                      </button>
                    </div>
                  )}

                  <button
                    onClick={() => {
                      setSessionId('');
                      localStorage.removeItem('JULES_SESSION_ID');
                    }}
                    className="w-full mt-4 py-2 text-sm text-gray-500 hover:text-gray-800 border border-gray-200 rounded-md hover:bg-gray-50 transition-colors"
                  >
                    Disconnect from Session
                  </button>
                </div>
              </div>

              {pollingError && (
                <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-start gap-3 shadow-sm">
                  <AlertTriangle size={20} className="shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-semibold">Connection Error</h4>
                    <p className="text-xs mt-1">{pollingError}</p>
                  </div>
                </div>
              )}

              {/* Verified Output / PR Handover */}
              {prLinks.length > 0 && (
                <div className="bg-white p-5 rounded-xl border border-green-200 shadow-sm relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-1 h-full bg-green-500"></div>
                  <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2 mb-3">
                    <Github size={16} /> PR Handover Ready
                  </h3>
                  <div className="space-y-2">
                    {Array.from(new Set(prLinks)).map((link, idx) => (
                      <a
                        key={idx}
                        href={link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded text-blue-600 hover:underline text-sm font-medium truncate"
                      >
                        {link}
                      </a>
                    ))}
                  </div>
                </div>
              )}

            </div>

            {/* Right Column: Activity Stream & Interaction */}
            <div className="lg:col-span-2 flex flex-col gap-4 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden h-[600px]">

              <div className="bg-slate-50 border-b border-gray-200 p-4 flex justify-between items-center">
                <h3 className="font-semibold text-gray-800">VM Execution Stream</h3>
                <button
                  onClick={refresh}
                  className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                >
                  <Loader2 size={12} className={pollingStatus === 'polling' ? 'animate-spin' : ''} />
                  Force Sync
                </button>
              </div>

              {/* Logs */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-sm">
                {activities.length === 0 ? (
                  <div className="text-gray-400 text-center mt-10 italic">
                    Waiting for initial telemetry from Jules VM...
                  </div>
                ) : (
                  [...activities].reverse().map((activity, idx) => (
                    <div key={idx} className="bg-gray-50 p-3 rounded-lg border border-gray-100">
                      <div className="flex items-center gap-2 text-xs text-gray-400 mb-2">
                        <span className="font-semibold text-indigo-500">[{activity.type}]</span>
                        <span>{new Date(activity.createTime).toLocaleTimeString()}</span>
                      </div>
                      <div className="whitespace-pre-wrap text-gray-700 break-words">
                        {activity.content}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Message Injection */}
              <div className="p-4 border-t border-gray-200 bg-white">
                <form onSubmit={handleSendMessage} className="flex gap-2">
                  <input
                    type="text"
                    value={taskPrompt}
                    onChange={(e) => setTaskPrompt(e.target.value)}
                    placeholder="Inject shell command (e.g., 'run npm test and report logs')..."
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <button
                    type="submit"
                    disabled={!taskPrompt}
                    className="px-4 py-2 bg-slate-800 text-white rounded-md hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    <Send size={16} /> Send
                  </button>
                </form>
              </div>
            </div>

          </div>
        )}

      </main>
    </div>
  );
}

export default App;

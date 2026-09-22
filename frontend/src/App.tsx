import { useCallback, useEffect, useState } from "react";
import { emergencyExit, fetchStatus, pause, resume, StatusResponse } from "./api";

const TOKEN_STORAGE_KEY = "adaptertrading_control_token";

function StateBadge({ state }: { state: string }) {
  const colors: Record<string, string> = {
    RUNNING: "bg-emerald-600",
    READY: "bg-emerald-700",
    PAUSED: "bg-amber-600",
    BLOCKED: "bg-red-700",
    EMERGENCY: "bg-red-900",
    RECONCILING: "bg-sky-700",
    WARMING_UP: "bg-sky-700",
    STARTING: "bg-slate-600",
    STOPPED: "bg-slate-700",
    UNKNOWN: "bg-slate-700",
  };
  return (
    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${colors[state] ?? "bg-slate-600"}`}>
      {state}
    </span>
  );
}

export default function App() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_STORAGE_KEY) ?? "");
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchStatus();
      setStatus(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 10_000);
    return () => clearInterval(interval);
  }, [load]);

  useEffect(() => {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  }, [token]);

  async function runAction(name: string, fn: (t: string) => Promise<unknown>) {
    if (!token) {
      setActionMessage("Informe o CONTROL_API_TOKEN antes de usar os controles.");
      return;
    }
    try {
      await fn(token);
      setActionMessage(`${name} executado com sucesso.`);
      load();
    } catch (e) {
      setActionMessage(`${name} falhou: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  return (
    <div className="min-h-screen p-6 max-w-3xl mx-auto space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">AdapterTrading</h1>
        {status && (
          <div className="flex items-center gap-3">
            <span className="text-slate-400 text-sm">{status.symbol}</span>
            <span className="uppercase text-xs px-2 py-1 rounded bg-slate-800 border border-slate-700">
              {status.trading_mode}
            </span>
          </div>
        )}
      </header>

      {error && (
        <div className="bg-red-950 border border-red-700 rounded p-3 text-sm">
          Erro ao consultar /status: {error}
        </div>
      )}

      {status && (
        <>
          <section className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Estado do Bot</h2>
              <StateBadge state={status.bot_state.state} />
            </div>
            <dl className="grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-slate-400">High-water mark</dt>
              <dd>{status.bot_state.high_water_mark ?? "-"}</dd>
              <dt className="text-slate-400">Equity de referência (dia)</dt>
              <dd>{status.bot_state.daily_reference_equity ?? "-"}</dd>
              <dt className="text-slate-400">Perdas consecutivas</dt>
              <dd>{status.bot_state.consecutive_losses}</dd>
              <dt className="text-slate-400">Resume manual necessário</dt>
              <dd>{status.bot_state.manual_resume_required ? "Sim" : "Não"}</dd>
              {status.bot_state.block_reason && (
                <>
                  <dt className="text-slate-400">Motivo do bloqueio</dt>
                  <dd className="text-red-400">{status.bot_state.block_reason}</dd>
                </>
              )}
            </dl>
          </section>

          <section className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">Posição</h2>
            {status.position ? (
              <dl className="grid grid-cols-2 gap-y-2 text-sm">
                <dt className="text-slate-400">Quantidade</dt>
                <dd>{status.position.quantity}</dd>
                <dt className="text-slate-400">Preço médio</dt>
                <dd>{status.position.average_entry}</dd>
                <dt className="text-slate-400">Stop</dt>
                <dd>{status.position.stop_price}</dd>
                <dt className="text-slate-400">Take profit</dt>
                <dd>{status.position.take_profit}</dd>
              </dl>
            ) : (
              <p className="text-slate-400 text-sm">Nenhuma posição aberta.</p>
            )}
          </section>

          <section className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">Último sinal</h2>
            {status.last_signal ? (
              <div className="text-sm space-y-1">
                <div>
                  Decisão: <span className="font-semibold">{status.last_signal.decision}</span>
                </div>
                <div className="text-slate-400">{status.last_signal.created_at}</div>
                {status.last_signal.reasons.length > 0 && (
                  <ul className="list-disc list-inside text-slate-400">
                    {status.last_signal.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <p className="text-slate-400 text-sm">Nenhum sinal registrado ainda.</p>
            )}
          </section>
        </>
      )}

      <section className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
        <h2 className="text-lg font-semibold">Controles</h2>
        <input
          type="password"
          placeholder="CONTROL_API_TOKEN"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm"
        />
        <div className="flex gap-3 flex-wrap">
          <button
            onClick={() => runAction("Pause", pause)}
            className="bg-amber-700 hover:bg-amber-600 px-4 py-2 rounded text-sm font-semibold"
          >
            Pause
          </button>
          <button
            onClick={() => runAction("Resume", resume)}
            className="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold"
          >
            Resume
          </button>
          <button
            onClick={() => {
              if (window.confirm("Confirma EMERGENCY EXIT? Isso fecha a posição real imediatamente.")) {
                runAction("Emergency Exit", emergencyExit);
              }
            }}
            className="bg-red-800 hover:bg-red-700 px-4 py-2 rounded text-sm font-semibold"
          >
            Emergency Exit
          </button>
        </div>
        {actionMessage && <p className="text-sm text-slate-300">{actionMessage}</p>}
      </section>
    </div>
  );
}

export interface StatusResponse {
  trading_mode: string;
  symbol: string;
  bot_state: {
    state: string;
    high_water_mark: string | null;
    daily_reference_equity: string | null;
    consecutive_losses: number;
    manual_resume_required: boolean;
    block_reason: string | null;
  };
  position: {
    quantity: string;
    average_entry: string;
    stop_price: string;
    take_profit: string;
    trailing_stop: string | null;
  } | null;
  last_signal: {
    decision: string;
    reasons: string[];
    created_at: string;
  } | null;
}

export async function fetchStatus(): Promise<StatusResponse> {
  const res = await fetch("/status");
  if (!res.ok) throw new Error(`status request failed: ${res.status}`);
  return res.json();
}

async function postControl(path: string, token: string): Promise<unknown> {
  const res = await fetch(`/control/${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${path} failed (${res.status}): ${body}`);
  }
  return res.json();
}

export const pause = (token: string) => postControl("pause", token);
export const resume = (token: string) => postControl("resume", token);
export const emergencyExit = (token: string) => postControl("emergency_exit", token);

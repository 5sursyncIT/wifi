interface OrderStatus {
  status?: string;
  entitlement_status: string;
}

interface PollOrderOptions {
  orderId: string;
  deadline: number;
  getOrder: (orderId: string) => Promise<OrderStatus>;
  onActive: () => Promise<void> | void;
  onExpired: () => void;
  onTerminal: () => void;
  now?: () => number;
  pollMs?: number;
  schedule?: (callback: () => void, delay: number) => void;
}

const TERMINAL = new Set<string | undefined>(["paid", "failed", "expired", "cancelled"]);

export async function pollOrder(options: PollOrderOptions): Promise<void> {
  const {
    orderId,
    deadline,
    getOrder,
    onActive,
    onExpired,
    onTerminal,
    now = Date.now,
    pollMs = 3000,
    schedule = window.setTimeout,
  } = options;

  if (now() > deadline) {
    onExpired();
    return;
  }

  let order: OrderStatus;
  try {
    order = await getOrder(orderId);
  } catch {
    schedule(() => void pollOrder(options), pollMs);
    return;
  }

  if (order.status === "paid") {
    if (order.entitlement_status === "active") {
      await onActive();
      return;
    }
  } else if (TERMINAL.has(order.status)) {
    onTerminal();
    return;
  }

  schedule(() => void pollOrder(options), pollMs);
}

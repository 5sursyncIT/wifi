import { describe, expect, it } from "vitest";

import { pollOrder } from "./purchase";

describe("pollOrder", () => {
  it("schedules another poll after a transient network error", async () => {
    let scheduledDelay: number | undefined;

    await pollOrder({
      orderId: "order-1",
      deadline: 10_000,
      getOrder: async () => {
        throw new TypeError("Network request failed");
      },
      onActive: () => undefined,
      onExpired: () => undefined,
      onTerminal: () => undefined,
      now: () => 1_000,
      schedule: (_callback, delay) => {
        scheduledDelay = delay;
      },
    });

    expect(scheduledDelay).toBe(3000);
  });
});

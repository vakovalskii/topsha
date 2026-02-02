import type { ServerEvent, ClientEvent } from "./agent/types.js";

export type { ClientEvent };

// Scheduler response from Rust
export type SchedulerResponse = {
  requestId: string;
  result: {
    success: boolean;
    data?: any;
    error?: string;
  };
};

export type SidecarInboundMessage =
  | { type: "client-event"; event: ClientEvent }
  | { type: "scheduler-response"; payload: SchedulerResponse };

export type SidecarOutboundMessage =
  | { type: "server-event"; event: ServerEvent }
  | { type: "log"; level: "info" | "error"; message: string; context?: Record<string, unknown> };


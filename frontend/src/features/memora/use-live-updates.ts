"use client";

import { useEffect, useEffectEvent } from "react";
import type { Access } from "./api";
import { subscribeUpdates } from "./realtime-client";

export function useLiveUpdates(refresh: () => void, meeting?: string, access: Access = {}) {
  const onRefresh = useEffectEvent(refresh);
  useEffect(() => subscribeUpdates(meeting, { token: access.token, password: access.password }, onRefresh), [meeting, access.token, access.password]);
}

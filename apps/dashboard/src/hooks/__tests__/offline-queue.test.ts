import { beforeEach, describe, expect, it } from "vitest";
import {
  addToSyncQueue,
  clearSyncQueue,
  readSyncQueue,
} from "@/lib/offline/shopping-list-cache";

describe("offline queue coalescing", () => {
  beforeEach(() => {
    clearSyncQueue();
  });

  it("dedupes updates by item_id within snapshots", () => {
    addToSyncQueue({
      action: "replay_snapshot",
      instanceIndex: "1",
      payload: { updates: [{ item_id: "a", status: "pending" }] },
    });
    addToSyncQueue({
      action: "replay_snapshot",
      instanceIndex: "1",
      payload: { updates: [{ item_id: "a", status: "purchased" }] },
    });
    const queue = readSyncQueue();
    expect(queue).toHaveLength(1);
    expect(queue[0].payload.updates).toEqual([
      expect.objectContaining({ item_id: "a", status: "purchased" }),
    ]);
  });

  it("merges granular update into existing snapshot", () => {
    addToSyncQueue({
      action: "replay_snapshot",
      instanceIndex: "1",
      payload: { updates: [{ item_id: "a", status: "pending" }] },
    });
    addToSyncQueue({
      action: "update_item",
      instanceIndex: "1",
      payload: { updates: [{ item_id: "b", status: "purchased" }] },
    });
    const queue = readSyncQueue();
    expect(queue).toHaveLength(1);
    expect(queue[0].payload.updates).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ item_id: "a" }),
        expect.objectContaining({ item_id: "b" }),
      ]),
    );
  });
});

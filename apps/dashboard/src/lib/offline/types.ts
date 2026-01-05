import type {
  BulkItemUpdate,
  ShoppingList,
  ShoppingListItem,
} from "@/lib/grocy/shopping-list-types";

export type StoredPayload<T> = {
  storedAt: number;
  data: T;
};

export type AddItemPayload = { product_id: number; quantity: number };
export type RemoveItemPayload = { item_ids: string[] };
export type UpdateItemPayload = { updates: BulkItemUpdate[] };
export type SnapshotPayload = { list: ShoppingList; updates: BulkItemUpdate[] };

export type PendingAction =
  | {
      id: string;
      timestamp: number;
      failureCount?: number;
      action: "add_item";
      instanceIndex: string;
      payload: AddItemPayload;
    }
  | {
      id: string;
      timestamp: number;
      failureCount?: number;
      action: "remove_item";
      instanceIndex: string;
      payload: RemoveItemPayload;
    }
  | {
      id: string;
      timestamp: number;
      failureCount?: number;
      action: "update_item";
      instanceIndex: string;
      payload: UpdateItemPayload;
    }
  | {
      id: string;
      timestamp: number;
      failureCount?: number;
      action: "replay_snapshot";
      instanceIndex: string;
      payload: SnapshotPayload;
    }
  | {
      id: string;
      timestamp: number;
      failureCount?: number;
      action: "complete_list" | "generate_list";
      instanceIndex: string;
      payload: Record<string, unknown>;
    };

export type PersistenceListener = (failed: boolean) => void;
export type ConnectivityListener = (online: boolean) => void;
export type SyncInfo = {
  lastSyncAt: number | null;
  queueSize: number;
  hadSyncDrop: boolean;
  lastError: string | null;
};
export type SyncListener = (info: SyncInfo) => void;

export type ListUpdateTarget = ShoppingList | ShoppingListItem;

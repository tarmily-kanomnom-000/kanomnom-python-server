export type RouteContext = {
  params: Promise<{
    instance_index: string;
    item_id?: string;
  }>;
};

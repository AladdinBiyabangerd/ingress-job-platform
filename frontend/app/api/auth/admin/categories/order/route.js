import { relay } from "../_relay";

export const runtime = "nodejs";

export async function PUT(request) {
  return relay(request, "/api/v1/admin/categories/order", "PUT", true);
}

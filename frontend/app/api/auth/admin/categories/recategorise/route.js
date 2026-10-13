import { relay } from "../_relay";

export const runtime = "nodejs";

export async function POST(request) {
  return relay(request, "/api/v1/admin/categories/recategorise", "POST");
}

import { relay } from "./_relay";

export const runtime = "nodejs";

export async function GET(request) {
  return relay(request, "/api/v1/admin/categories");
}

export async function POST(request) {
  return relay(request, "/api/v1/admin/categories", "POST", true);
}

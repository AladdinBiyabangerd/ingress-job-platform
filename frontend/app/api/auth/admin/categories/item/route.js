import { noStore } from "../../../../../../lib/server/oidc";
import { relay } from "../_relay";

export const runtime = "nodejs";

/** PATCH /api/auth/admin/categories/item?slug=DevOps%2FCloud */
export async function PATCH(request) {
  const slug = new URL(request.url).searchParams.get("slug") || "";
  if (!slug || slug.length > 40) return noStore(Response.json({ detail: "not_found" }, { status: 404 }));
  const path = `/api/v1/admin/categories/${slug.split("/").map(encodeURIComponent).join("/")}`;
  return relay(request, path, "PATCH", true);
}

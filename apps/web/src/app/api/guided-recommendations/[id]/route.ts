import { forwardGuided } from "@/features/guided-builder/proxy";

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  return forwardGuided(`/${encodeURIComponent(id)}`, { method: "GET" });
}

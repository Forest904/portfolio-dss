import { forwardGuided } from "@/features/guided-builder/proxy";

export async function POST(request: Request) {
  return forwardGuided("", { method: "POST", headers: { "Content-Type": "application/json" }, body: await request.text() });
}

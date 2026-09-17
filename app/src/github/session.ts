import { cookies } from "next/headers";

import { githubOAuthConfig, INSTALLATION_COOKIE, verifyInstallationCookie } from "./auth";

// The connected installation for a server-rendered page, or null when GitHub
// is not configured or the visitor has not connected. API routes keep their
// own explicit 401 handling.
export async function connectedInstallationId(): Promise<number | null> {
  let secret: string;
  try {
    secret = githubOAuthConfig().sessionSecret;
  } catch {
    return null;
  }
  const cookieStore = await cookies();
  return verifyInstallationCookie(cookieStore.get(INSTALLATION_COOKIE)?.value, secret);
}

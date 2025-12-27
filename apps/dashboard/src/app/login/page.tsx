import type { Metadata } from "next";
import { redirect } from "next/navigation";
import type { JSX } from "react";

import { LoginForm } from "@/components/auth/login-form";
import { LoginRedirectGuard } from "@/components/auth/login-redirect-guard";
import { resolveCallbackPath } from "@/lib/auth/redirect";
import { getCurrentSession } from "@/lib/auth/session";

export const metadata: Metadata = {
  title: "Sign in | Ka-Nom Nom Dashboard",
};

export const dynamic = "force-dynamic";
export const revalidate = 0;

type LoginPageProps = {
  searchParams?: Promise<{ callbackUrl?: string | string[] }>;
};

export default async function LoginPage({
  searchParams,
}: LoginPageProps): Promise<JSX.Element> {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const requestedRedirect =
    resolveCallbackPath(resolvedSearchParams?.callbackUrl) ?? "/";
  const session = await getCurrentSession();
  if (session) {
    redirect(requestedRedirect);
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-100 px-4 py-12">
      <LoginRedirectGuard targetPath={requestedRedirect} />
      <LoginForm callbackUrl={requestedRedirect} />
    </main>
  );
}

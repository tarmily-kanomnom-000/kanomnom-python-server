"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import type React from "react";
import { useState } from "react";

import { resolveCallbackPath } from "@/lib/auth/redirect";

type LoginFormProps = {
  callbackUrl?: string | null;
};

export function LoginForm({ callbackUrl = null }: LoginFormProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);
  const fallbackRedirect =
    resolveCallbackPath(searchParams.get("callbackUrl")) ?? "/";
  const redirectTarget = resolveCallbackPath(callbackUrl) ?? fallbackRedirect;

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const result = await signIn("credentials", {
      redirect: false,
      username,
      password,
      callbackUrl: redirectTarget,
    });
    setSubmitting(false);
    if (!result || result.error || result.ok === false) {
      setError("Invalid username or password.");
      return;
    }
    // Use a hard navigation so the server-side session check (and proxy) see the fresh cookie immediately.
    router.replace(redirectTarget);
    router.refresh();
  };

  return (
    <form
      className="mx-auto w-full max-w-md space-y-6 rounded-3xl border border-neutral-200 bg-white p-8 shadow-sm"
      onSubmit={handleSubmit}
    >
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wide text-neutral-500">
          Access required
        </p>
        <h1 className="text-2xl font-semibold text-neutral-900">
          Sign in to Ka-Nom Nom
        </h1>
        <p className="text-sm text-neutral-600">
          Use your dashboard credentials. Admins can manage Grocy inventory;
          viewers can browse stock.
        </p>
      </div>

      <div className="space-y-4">
        <label className="block text-sm font-medium text-neutral-800">
          Username
          <input
            type="text"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="mt-1 w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
            required
          />
        </label>
        <label className="block text-sm font-medium text-neutral-800">
          Password
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
            required
          />
        </label>
      </div>

      {error ? (
        <p className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-full bg-neutral-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-70"
      >
        {isSubmitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useEffect } from "react";

type LoginRedirectGuardProps = {
  targetPath: string;
};

export function LoginRedirectGuard({
  targetPath,
}: LoginRedirectGuardProps): null {
  const { status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") {
      router.replace(targetPath);
    }
  }, [router, status, targetPath]);

  return null;
}

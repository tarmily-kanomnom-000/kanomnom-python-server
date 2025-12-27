import { withAuth } from "next-auth/middleware";

export default withAuth({
  callbacks: {
    authorized: ({ token }) => Boolean(token),
  },
  pages: {
    signIn: "/login",
  },
});

export const config = {
  matcher: [
    "/((?!api/auth|login|_next/|favicon\\.ico|manifest\\.json|robots\\.txt|sw\\.js|service-worker\\.js|.*\\.(?:png|jpg|jpeg|svg|gif|ico)$).*)",
  ],
};

import { auth } from '@/lib/auth';
import { NextResponse } from 'next/server';

// Public paths that don't require authentication
const PUBLIC_PATHS = ['/login', '/api/auth', '/verify-email'];

// Paths that require admin role
const ADMIN_PATHS = ['/admin'];

export default auth((req) => {
  const { pathname } = req.nextUrl;
  const isLoggedIn = !!req.auth;

  // Check if path is public
  const isPublicPath = PUBLIC_PATHS.some((path) => pathname.startsWith(path));

  // Allow public API routes
  if (isPublicPath) {
    // If logged in and on login page, redirect to home
    if (isLoggedIn && pathname === '/login') {
      return NextResponse.redirect(new URL('/', req.nextUrl));
    }
    return NextResponse.next();
  }

  // Require authentication for all other paths
  if (!isLoggedIn) {
    // API routes return 401
    if (pathname.startsWith('/api')) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Pages redirect to login
    const callbackUrl = encodeURIComponent(pathname);
    return NextResponse.redirect(new URL(`/login?callbackUrl=${callbackUrl}`, req.nextUrl));
  }

  // Check for admin-only paths
  const isAdminPath = ADMIN_PATHS.some((path) => pathname.startsWith(path));
  if (isAdminPath) {
    const roles = (req.auth?.user as { roles?: string[] })?.roles || [];
    const isAdmin = roles.includes('admin');

    if (!isAdmin) {
      // Not admin, redirect to home with error
      return NextResponse.redirect(new URL('/?error=AccessDenied', req.nextUrl));
    }
  }

  // Check for email verification (if configured)
  const emailVerified = (req.auth?.user as { emailVerified?: boolean })?.emailVerified;
  if (emailVerified === false && !pathname.startsWith('/verify-email')) {
    return NextResponse.redirect(new URL('/verify-email', req.nextUrl));
  }

  // Check for onboarding requirement
  const requiresOnboarding = (req.auth as { requiresOnboarding?: boolean })?.requiresOnboarding;
  if (requiresOnboarding && !pathname.startsWith('/onboarding')) {
    return NextResponse.redirect(new URL('/onboarding', req.nextUrl));
  }

  // Allow request to proceed
  return NextResponse.next();
});

export const config = {
  // Match all routes except static files and _next
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)'],
};

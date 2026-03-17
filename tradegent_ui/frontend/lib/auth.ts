import NextAuth from 'next-auth';
import Auth0 from 'next-auth/providers/auth0';
import Google from 'next-auth/providers/google';
import Credentials from 'next-auth/providers/credentials';
import type { NextAuthConfig } from 'next-auth';
import type { JWT } from 'next-auth/jwt';

/**
 * Auth configuration for Tradegent UI with Auth0.
 *
 * Supports:
 * - Auth0 Universal Login (Google, GitHub, email/password)
 * - Token refresh with rotation
 * - Role-based access control via Auth0 Actions
 * - Fallback to demo users for development without Auth0
 */

// Environment variables
const AUTH0_CLIENT_ID = process.env.AUTH0_CLIENT_ID;
const AUTH0_CLIENT_SECRET = process.env.AUTH0_CLIENT_SECRET;
const AUTH0_ISSUER = process.env.AUTH0_ISSUER_BASE_URL;
const AUTH0_AUDIENCE = process.env.AUTH0_AUDIENCE || 'https://tradegent-api.local';
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID;
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET;
const JWT_SECRET = process.env.JWT_SECRET || process.env.AUTH_SECRET;

// Check if Auth0 is configured
const isAuth0Configured = !!(AUTH0_CLIENT_ID && AUTH0_CLIENT_SECRET && AUTH0_ISSUER);
const isGoogleConfigured = !!(GOOGLE_CLIENT_ID && GOOGLE_CLIENT_SECRET);

const ADMIN_PERMISSIONS = [
  'read:portfolio', 'write:portfolio',
  'read:trades', 'write:trades',
  'read:analyses', 'write:analyses',
  'read:watchlist', 'write:watchlist',
  'read:knowledge', 'write:knowledge',
  'admin:users', 'admin:system', 'admin:settings',
];

const TRADER_PERMISSIONS = [
  'read:portfolio', 'write:portfolio',
  'read:trades', 'write:trades',
  'read:analyses', 'write:analyses',
  'read:watchlist', 'write:watchlist',
  'read:knowledge', 'write:knowledge',
];

function toBase64Url(input: string | Uint8Array): string {
  const bytes = typeof input === 'string' ? new TextEncoder().encode(input) : input;
  let binary = '';
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }

  const base64 = typeof btoa === 'function'
    ? btoa(binary)
    : Buffer.from(bytes).toString('base64');

  return base64
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

async function createBuiltinAccessToken(user: {
  id: string;
  subject?: string;
  email?: string | null;
  name?: string | null;
  roles?: string[];
  permissions?: string[];
}): Promise<string> {
  if (!JWT_SECRET) {
    throw new Error('JWT_SECRET is not configured for built-in auth token signing');
  }

  const userId = user.subject ?? (user.id === 'admin' ? 'builtin|admin' : 'builtin|demo');
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    sub: userId,
    email: user.email ?? '',
    name: user.name ?? '',
    roles: user.roles ?? [],
    permissions: user.permissions ?? [],
    iat: now,
    exp: now + 24 * 60 * 60,
  };

  const header = { alg: 'HS256', typ: 'JWT' };
  const encodedHeader = toBase64Url(JSON.stringify(header));
  const encodedPayload = toBase64Url(JSON.stringify(payload));
  const content = `${encodedHeader}.${encodedPayload}`;
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(JWT_SECRET),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const signature = await crypto.subtle.sign(
    'HMAC',
    key,
    new TextEncoder().encode(content)
  );

  return `${content}.${toBase64Url(new Uint8Array(signature))}`;
}

// Built-in account credentials from environment
// Admin user is like PostgreSQL's postgres user - a superuser that always exists
// SECURITY: All credentials MUST be set via environment variables - no defaults
const ADMIN_EMAIL = process.env.ADMIN_EMAIL || 'admin@tradegent.local';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
const ADMIN_NAME = process.env.ADMIN_NAME || 'System Administrator';
const DEMO_EMAIL = process.env.DEMO_EMAIL || 'demo@tradegent.local';
const DEMO_PASSWORD = process.env.DEMO_PASSWORD;

// Validate required credentials at module load
if (!ADMIN_PASSWORD) {
  console.error('SECURITY ERROR: ADMIN_PASSWORD environment variable is not set');
}
if (!DEMO_PASSWORD && DEMO_EMAIL) {
  console.warn('Warning: DEMO_PASSWORD not set - demo account will be disabled');
}

// Built-in users (used when Auth0 is not configured)
const BUILTIN_USERS = [
  {
    id: 'admin',
    name: ADMIN_NAME,
    email: ADMIN_EMAIL,
    password: ADMIN_PASSWORD,
    roles: ['admin'],
    permissions: ADMIN_PERMISSIONS,
  },
  {
    id: 'demo',
    name: 'Demo Trader',
    email: DEMO_EMAIL,
    password: DEMO_PASSWORD,
    roles: ['trader'],
    permissions: TRADER_PERMISSIONS,
  },
];

function resolveDefaultAccessByEmail(email?: string | null): {
  roles: string[];
  permissions: string[];
} {
  if (email && email.toLowerCase() === ADMIN_EMAIL.toLowerCase()) {
    return { roles: ['admin'], permissions: ADMIN_PERMISSIONS };
  }

  return { roles: ['trader'], permissions: TRADER_PERMISSIONS };
}

function getSafeCallbackPath(raw: string | null): string {
  if (!raw) {
    return '/';
  }

  const decoded = decodeURIComponent(raw);

  // Only allow same-origin relative paths to prevent open redirects.
  if (decoded.startsWith('/') && !decoded.startsWith('//')) {
    return decoded;
  }

  return '/';
}

/**
 * Refresh an expired access token using Auth0
 */
async function refreshAccessToken(token: JWT): Promise<JWT> {
  if (!AUTH0_ISSUER || !AUTH0_CLIENT_ID || !AUTH0_CLIENT_SECRET) {
    console.error('Auth0 not configured for token refresh');
    return { ...token, error: 'RefreshAccessTokenError' as const };
  }

  try {
    const response = await fetch(`${AUTH0_ISSUER}/oauth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        client_id: AUTH0_CLIENT_ID,
        client_secret: AUTH0_CLIENT_SECRET,
        refresh_token: token.refreshToken as string,
      }),
    });

    const refreshedTokens = await response.json();

    if (!response.ok) {
      console.error('Failed to refresh token:', refreshedTokens);
      return { ...token, error: 'RefreshAccessTokenError' as const };
    }

    return {
      ...token,
      accessToken: refreshedTokens.access_token,
      expiresAt: Math.floor(Date.now() / 1000) + refreshedTokens.expires_in,
      refreshToken: refreshedTokens.refresh_token ?? token.refreshToken,
    };
  } catch (error) {
    console.error('Error refreshing access token:', error);
    return { ...token, error: 'RefreshAccessTokenError' as const };
  }
}

// Build providers array
const providers: NextAuthConfig['providers'] = [];

// Add Auth0 provider if configured
if (isAuth0Configured) {
  providers.push(
    Auth0({
      clientId: AUTH0_CLIENT_ID!,
      clientSecret: AUTH0_CLIENT_SECRET!,
      issuer: AUTH0_ISSUER!,
      authorization: {
        params: {
          audience: AUTH0_AUDIENCE,
          scope: 'openid profile email offline_access',
        },
      },
    })
  );
}

// Add Google provider if configured
if (isGoogleConfigured) {
  providers.push(
    Google({
      clientId: GOOGLE_CLIENT_ID!,
      clientSecret: GOOGLE_CLIENT_SECRET!,
    })
  );
}

// Always add Credentials provider for built-in authentication
providers.push(
  Credentials({
    id: 'credentials',
    name: 'Built-in Login',
    credentials: {
      email: { label: 'Email', type: 'email' },
      password: { label: 'Password', type: 'password' },
    },
    async authorize(credentials) {
      if (!credentials?.email || !credentials?.password) {
        return null;
      }

      // SECURITY: Reject login attempts if passwords are not configured
      // This prevents default credential attacks
      const user = BUILTIN_USERS.find(
        (u) =>
          u.email.toLowerCase() === (credentials.email as string).toLowerCase() &&
          u.password && // Password must be set (not undefined/null)
          u.password === credentials.password
      );

      if (!user) {
        return null;
      }

      return {
        id: user.id,
        name: user.name,
        email: user.email,
        roles: user.roles,
        permissions: user.permissions,
        emailVerified: true,
      };
    },
  })
);

export const authConfig: NextAuthConfig = {
  pages: {
    signIn: '/login',
    error: '/login',
  },
  providers,
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user;
      const isOnLogin = nextUrl.pathname.startsWith('/login');
      const isOnOnboarding = nextUrl.pathname.startsWith('/onboarding');
      const isOnVerifyEmail = nextUrl.pathname.startsWith('/verify-email');

      // Allow login and verify-email pages
      if (isOnLogin || isOnVerifyEmail) {
        if (isLoggedIn && !isOnVerifyEmail) {
          const callbackPath = getSafeCallbackPath(nextUrl.searchParams.get('callbackUrl'));
          return Response.redirect(new URL(callbackPath, nextUrl));
        }
        return true;
      }

      // Require login for all other pages
      if (!isLoggedIn) {
        return false;
      }

      // Check for onboarding requirement
      const requiresOnboarding = (auth as { requiresOnboarding?: boolean })?.requiresOnboarding;
      if (requiresOnboarding && !isOnOnboarding) {
        return Response.redirect(new URL('/onboarding', nextUrl));
      }

      return true;
    },

    async jwt({ token, user, account }) {
      // Initial sign-in
      if (account && user) {
        // Auth0 login
        if (account.provider === 'auth0') {
          return {
            ...token,
            accessToken: account.access_token,
            refreshToken: account.refresh_token,
            expiresAt: account.expires_at,
            roles: (user as { roles?: string[] }).roles || [],
            permissions: (user as { permissions?: string[] }).permissions || [],
            emailVerified: (user as { emailVerified?: boolean }).emailVerified ?? true,
          };
        }

        // Google OAuth login (direct provider)
        if (account.provider === 'google') {
          const defaults = resolveDefaultAccessByEmail(user.email);
          const subject = `google|${String(user.id)}`;
          const builtinToken = await createBuiltinAccessToken({
            id: String(user.id),
            subject,
            email: user.email,
            name: user.name,
            roles: defaults.roles,
            permissions: defaults.permissions,
          });

          return {
            ...token,
            accessToken: builtinToken,
            // Store the prefixed subject so the renewal path can use it.
            builtinSub: subject,
            expiresAt: Math.floor(Date.now() / 1000) + 24 * 60 * 60,
            roles: defaults.roles,
            permissions: defaults.permissions,
            emailVerified: true,
          };
        }

        // Credentials login (builtin admin/demo)
        // createBuiltinAccessToken maps id='admin' → sub='builtin|admin',
        // id='demo' → sub='builtin|demo'. Store that mapping in builtinSub.
        const credentialsId = String(user.id);
        const credentialsBuiltinSub =
          credentialsId === 'admin' ? 'builtin|admin' : 'builtin|demo';
        const builtinToken = await createBuiltinAccessToken({
          id: credentialsId,
          email: user.email,
          name: user.name,
          roles: (user as { roles?: string[] }).roles || [],
          permissions: (user as { permissions?: string[] }).permissions || [],
        });

        return {
          ...token,
          accessToken: builtinToken,
          builtinSub: credentialsBuiltinSub,
          expiresAt: Math.floor(Date.now() / 1000) + 24 * 60 * 60,
          roles: (user as { roles?: string[] }).roles || [],
          permissions: (user as { permissions?: string[] }).permissions || [],
          emailVerified: true,
        };
      }

      // Return existing token if not expired
      if (token.expiresAt && Date.now() < (token.expiresAt as number) * 1000) {
        return token;
      }

      // Refresh expired token (only for Auth0)
      if (token.refreshToken) {
        return await refreshAccessToken(token);
      }

      // Regenerate builtin access token (credentials/google users have no refreshToken).
      // This handles: (a) existing sessions missing expiresAt, and (b) expired builtin tokens.
      // builtinSub holds the correctly-prefixed subject ('builtin|admin', 'google|xxx', etc.).
      // Fall back to deriving it from token.sub for legacy sessions without builtinSub.
      // Validate that builtinSub is properly prefixed; re-derive if it's a raw id
      // (handles legacy sessions and the brief window where a bad value may have been stored).
      const rawBuiltinSub = token.builtinSub as string | undefined;
      const builtinSub =
        rawBuiltinSub &&
        (rawBuiltinSub.startsWith('builtin|') || rawBuiltinSub.startsWith('google|'))
          ? rawBuiltinSub
          : (() => {
              const s = token.sub ?? '';
              if (s === 'admin' || s === 'builtin') return 'builtin|admin';
              if (s === 'demo') return 'builtin|demo';
              return s; // already a prefixed id (e.g. 'builtin|admin')
            })();
      try {
        const renewedToken = await createBuiltinAccessToken({
          id: builtinSub,
          subject: builtinSub,
          email: token.email as string | null,
          name: token.name as string | null,
          roles: (token.roles as string[]) || [],
          permissions: (token.permissions as string[]) || [],
        });
        return {
          ...token,
          accessToken: renewedToken,
          builtinSub,
          expiresAt: Math.floor(Date.now() / 1000) + 24 * 60 * 60,
        };
      } catch {
        return { ...token, error: 'RefreshAccessTokenError' };
      }
    },

    async session({ session, token }) {
      // Add access token to session
      session.accessToken = token.accessToken as string;
      session.error = token.error;

      // Add user info
      if (session.user) {
        session.user.id = token.sub!;
        session.user.roles = (token.roles as string[]) || [];
        session.user.permissions = (token.permissions as string[]) || [];
        // NextAuth v5 types emailVerified as a complex intersection (Date & bool);
        // cast through unknown to set Date | null without triggering adapter type errors.
        (session.user as unknown as Record<string, unknown>).emailVerified =
          token.emailVerified ? new Date() : null;
      }

      return session;
    },
  },

  events: {
    async signOut() {
      // Auth0 federated logout is handled in the frontend
      // See user-menu.tsx handleSignOut function
    },
  },

  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },

  trustHost: true,
  debug: process.env.NODE_ENV === 'development',
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);

// Export Auth0 config for use in components
export const auth0Config = {
  isConfigured: isAuth0Configured,
  issuer: AUTH0_ISSUER,
  clientId: AUTH0_CLIENT_ID,
  audience: AUTH0_AUDIENCE,
};

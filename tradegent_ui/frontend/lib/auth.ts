import NextAuth from 'next-auth';
import Auth0 from 'next-auth/providers/auth0';
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

// Check if Auth0 is configured
const isAuth0Configured = !!(AUTH0_CLIENT_ID && AUTH0_CLIENT_SECRET && AUTH0_ISSUER);

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
    permissions: [
      'read:portfolio', 'write:portfolio',
      'read:trades', 'write:trades',
      'read:analyses', 'write:analyses',
      'read:watchlist', 'write:watchlist',
      'read:knowledge', 'write:knowledge',
      'admin:users', 'admin:system', 'admin:settings',
    ],
  },
  {
    id: 'demo',
    name: 'Demo Trader',
    email: DEMO_EMAIL,
    password: DEMO_PASSWORD,
    roles: ['trader'],
    permissions: [
      'read:portfolio', 'write:portfolio',
      'read:trades', 'write:trades',
      'read:analyses', 'write:analyses',
      'read:watchlist', 'write:watchlist',
      'read:knowledge', 'write:knowledge',
    ],
  },
];

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
          return Response.redirect(new URL('/', nextUrl));
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

        // Credentials login (demo)
        return {
          ...token,
          accessToken: `demo-token-${user.id}`,
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

      return token;
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
        session.user.emailVerified = token.emailVerified as boolean;
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

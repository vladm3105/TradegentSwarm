/**
 * Auth0 Multi-User Types for Tradegent UI
 */

// User session from Auth0
export interface UserSession {
  id: string;           // Auth0 sub (e.g., "auth0|123" or "google-oauth2|456")
  email: string;
  name?: string;
  picture?: string;
  roles: string[];      // ['admin', 'trader', etc.]
  permissions: string[]; // ['read:portfolio', 'write:trades', etc.]
  emailVerified?: boolean;
  ib_account_id?: string;
  ib_trading_mode?: 'paper' | 'live';
}

// Extend NextAuth types
declare module 'next-auth' {
  interface Session {
    user: UserSession;
    accessToken: string;
    refreshToken?: string;
    expiresAt?: number;
    requiresOnboarding?: boolean;
    error?: 'RefreshAccessTokenError';
  }

  interface User {
    id: string;
    email: string;
    name?: string;
    picture?: string;
    roles?: string[];
    permissions?: string[];
    emailVerified?: boolean;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    expiresAt?: number;
    roles?: string[];
    permissions?: string[];
    emailVerified?: boolean;
    error?: 'RefreshAccessTokenError';
  }
}

// API context passed with requests
export interface ApiContext {
  user_id: number;
  permissions: string[];
}

// Role definitions
export type Role = 'admin' | 'trader' | 'analyst' | 'viewer';

// Permission codes
export type Permission =
  | 'read:portfolio'
  | 'write:portfolio'
  | 'read:trades'
  | 'write:trades'
  | 'read:analyses'
  | 'write:analyses'
  | 'read:watchlist'
  | 'write:watchlist'
  | 'read:knowledge'
  | 'write:knowledge'
  | 'admin:users'
  | 'admin:system';

// Permission check helper
export function hasPermission(
  permissions: string[] | undefined,
  required: Permission
): boolean {
  return permissions?.includes(required) ?? false;
}

// Role check helper
export function hasRole(roles: string[] | undefined, required: Role): boolean {
  return roles?.includes(required) ?? false;
}

// Check if user is admin
export function isAdmin(roles: string[] | undefined): boolean {
  return hasRole(roles, 'admin');
}

// Auth0 error types
export type Auth0Error =
  | 'access_denied'
  | 'invalid_token'
  | 'expired_token'
  | 'insufficient_scope'
  | 'account_deactivated'
  | 'email_not_verified'
  | 'RefreshAccessTokenError';

// Auth0 callback URL params
export interface Auth0CallbackParams {
  code?: string;
  state?: string;
  error?: string;
  error_description?: string;
}

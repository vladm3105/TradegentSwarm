'use client';

import { signOut, useSession } from 'next-auth/react';
import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  User,
  LogOut,
  Settings,
  Key,
  Shield,
  Loader2,
  ChevronDown,
} from 'lucide-react';
import { hasRole } from '@/types/auth';

// Auth0 config from env
const AUTH0_ISSUER = process.env.NEXT_PUBLIC_AUTH0_ISSUER;
const AUTH0_CLIENT_ID = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID;
const AUTH0_BASE_URL = process.env.NEXT_PUBLIC_AUTH0_BASE_URL || 'http://localhost:3001';

export function UserMenu() {
  const { data: session, status } = useSession();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  if (status === 'loading') {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
      </div>
    );
  }

  if (!session?.user) {
    return null;
  }

  const handleSignOut = async () => {
    setIsLoggingOut(true);

    // For Auth0, perform federated logout
    if (AUTH0_ISSUER && AUTH0_CLIENT_ID && session.accessToken?.startsWith('ey')) {
      // Build Auth0 logout URL
      const logoutUrl = new URL(`${AUTH0_ISSUER}/v2/logout`);
      logoutUrl.searchParams.set('client_id', AUTH0_CLIENT_ID);
      logoutUrl.searchParams.set('returnTo', AUTH0_BASE_URL);

      // Sign out from NextAuth first, then redirect to Auth0 logout
      await signOut({ redirect: false });
      window.location.href = logoutUrl.toString();
    } else {
      // Regular logout for demo/credentials
      await signOut({ callbackUrl: '/login' });
    }
  };

  const user = session.user;
  const isAdmin = hasRole(user.roles, 'admin');

  // Get initials for avatar
  const getInitials = (name?: string | null): string => {
    if (!name) return 'U';
    const parts = name.split(' ');
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return name[0].toUpperCase();
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="flex items-center gap-2 px-2">
          {/* Avatar */}
          <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center overflow-hidden">
            {user.picture ? (
              <img
                src={user.picture}
                alt={user.name || 'User'}
                className="h-full w-full object-cover"
              />
            ) : (
              <span className="text-sm font-medium text-primary">
                {getInitials(user.name)}
              </span>
            )}
          </div>

          {/* Name and role */}
          <div className="hidden sm:block text-left">
            <p className="text-sm font-medium leading-none">{user.name}</p>
            <p className="text-xs text-muted-foreground capitalize">
              {user.roles?.[0] || 'User'}
            </p>
          </div>

          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium">{user.name}</p>
            <p className="text-xs text-muted-foreground">{user.email}</p>
          </div>
        </DropdownMenuLabel>

        <DropdownMenuSeparator />

        <DropdownMenuItem asChild>
          <Link href="/settings/profile" className="cursor-pointer">
            <User className="mr-2 h-4 w-4" />
            Profile
          </Link>
        </DropdownMenuItem>

        <DropdownMenuItem asChild>
          <Link href="/settings/ib-account" className="cursor-pointer">
            <Settings className="mr-2 h-4 w-4" />
            IB Account
          </Link>
        </DropdownMenuItem>

        <DropdownMenuItem asChild>
          <Link href="/settings/api-keys" className="cursor-pointer">
            <Key className="mr-2 h-4 w-4" />
            API Keys
          </Link>
        </DropdownMenuItem>

        {isAdmin && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/admin/users" className="cursor-pointer">
                <Shield className="mr-2 h-4 w-4" />
                User Management
              </Link>
            </DropdownMenuItem>
          </>
        )}

        <DropdownMenuSeparator />

        <DropdownMenuItem
          onClick={handleSignOut}
          disabled={isLoggingOut}
          className="cursor-pointer text-loss focus:text-loss"
        >
          {isLoggingOut ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Signing out...
            </>
          ) : (
            <>
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </>
          )}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

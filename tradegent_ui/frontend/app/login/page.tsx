'use client';

import { useState } from 'react';
import { signIn } from 'next-auth/react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AlertCircle, Loader2, Github, Mail, KeyRound } from 'lucide-react';

// Check if Auth0 is configured via env
const AUTH0_CONFIGURED = !!process.env.NEXT_PUBLIC_AUTH0_CONFIGURED;

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showCredentialsLogin, setShowCredentialsLogin] = useState(!AUTH0_CONFIGURED);
  const searchParams = useSearchParams();
  const router = useRouter();

  const callbackUrl = searchParams.get('callbackUrl') || '/';
  const authError = searchParams.get('error');

  // Map Auth0 error codes to messages
  const getErrorMessage = (error: string | null): string => {
    switch (error) {
      case 'AccessDenied':
        return 'Access denied. Please contact support.';
      case 'Configuration':
        return 'Auth configuration error. Please try again.';
      case 'Verification':
        return 'Please verify your email before signing in.';
      case 'OAuthAccountNotLinked':
        return 'Email already used with different provider.';
      case 'RefreshAccessTokenError':
        return 'Session expired. Please sign in again.';
      default:
        return error || '';
    }
  };

  // Handle Auth0 login
  const handleAuth0Login = async () => {
    setIsLoading(true);
    setError('');
    await signIn('auth0', { callbackUrl });
  };

  // Handle demo/credentials login
  const handleCredentialsLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false,
        callbackUrl,
      });

      if (result?.error) {
        setError('Invalid email or password');
      } else if (result?.url) {
        router.push(result.url);
        router.refresh();
      }
    } catch {
      setError('An error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <div className="h-12 w-12 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-2xl">T</span>
            </div>
          </div>
          <CardTitle className="text-2xl font-bold">Welcome to Tradegent</CardTitle>
          <CardDescription>
            Sign in to access your trading dashboard
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Show Auth0 error if present */}
          {(authError || error) && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-loss/10 text-loss text-sm">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{error || getErrorMessage(authError)}</span>
            </div>
          )}

          {/* Auth0 Login Buttons */}
          {AUTH0_CONFIGURED && (
            <>
              <Button
                type="button"
                className="w-full"
                onClick={handleAuth0Login}
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Signing in...
                  </>
                ) : (
                  <>
                    <KeyRound className="h-4 w-4 mr-2" />
                    Sign in with Auth0
                  </>
                )}
              </Button>

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-background px-2 text-muted-foreground">
                    Or continue with
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => signIn('auth0', {
                    callbackUrl,
                    authorizationParams: { connection: 'google-oauth2' }
                  })}
                  disabled={isLoading}
                >
                  <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24">
                    <path
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      fill="#4285F4"
                    />
                    <path
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      fill="#34A853"
                    />
                    <path
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      fill="#FBBC05"
                    />
                    <path
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      fill="#EA4335"
                    />
                  </svg>
                  Google
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => signIn('auth0', {
                    callbackUrl,
                    authorizationParams: { connection: 'github' }
                  })}
                  disabled={isLoading}
                >
                  <Github className="h-4 w-4 mr-2" />
                  GitHub
                </Button>
              </div>

              {/* Toggle to show email/password login */}
              <Button
                type="button"
                variant="link"
                className="w-full text-muted-foreground"
                onClick={() => setShowCredentialsLogin(!showCredentialsLogin)}
              >
                {showCredentialsLogin ? 'Hide' : 'Show'} email login
              </Button>
            </>
          )}

          {/* Email/Password Login Form */}
          {showCredentialsLogin && (
            <>
              {AUTH0_CONFIGURED && (
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-background px-2 text-muted-foreground">
                      Email login
                    </span>
                  </div>
                </div>
              )}

              <form onSubmit={handleCredentialsLogin} className="space-y-4">
                <div className="space-y-2">
                  <label htmlFor="email" className="text-sm font-medium">
                    Email
                  </label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isLoading}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <label htmlFor="password" className="text-sm font-medium">
                    Password
                  </label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isLoading}
                    required
                  />
                </div>

                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Signing in...
                    </>
                  ) : (
                    <>
                      <Mail className="h-4 w-4 mr-2" />
                      Sign In
                    </>
                  )}
                </Button>
              </form>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

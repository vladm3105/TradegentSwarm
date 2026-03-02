'use client';

import { signOut } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Mail, RefreshCw, LogOut } from 'lucide-react';

export default function VerifyEmailPage() {
  const handleResendVerification = async () => {
    // Auth0 handles email verification via their dashboard/API
    // This would typically call an API endpoint that triggers Auth0 to resend
    window.open('https://auth0.com/docs/customize/email/email-templates', '_blank');
  };

  const handleSignOut = async () => {
    await signOut({ callbackUrl: '/login' });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
              <Mail className="h-8 w-8 text-primary" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold">Verify Your Email</CardTitle>
          <CardDescription>
            We've sent a verification email to your inbox
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="text-center space-y-2">
            <p className="text-muted-foreground">
              Please click the link in the email to verify your account.
              If you don't see the email, check your spam folder.
            </p>
          </div>

          <div className="space-y-3">
            <Button
              variant="outline"
              className="w-full"
              onClick={handleResendVerification}
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Resend Verification Email
            </Button>

            <Button
              variant="ghost"
              className="w-full"
              onClick={handleSignOut}
            >
              <LogOut className="h-4 w-4 mr-2" />
              Sign Out
            </Button>
          </div>

          <p className="text-xs text-muted-foreground text-center">
            After verifying your email, refresh this page or sign in again.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

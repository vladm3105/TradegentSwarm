'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
  Briefcase,
  Bell,
  Palette,
  Rocket,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';

const STEPS = [
  { id: 'welcome', title: 'Welcome', icon: Rocket },
  { id: 'ib-account', title: 'IB Account', icon: Briefcase },
  { id: 'preferences', title: 'Preferences', icon: Palette },
  { id: 'notifications', title: 'Notifications', icon: Bell },
  { id: 'complete', title: 'Complete', icon: CheckCircle2 },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { data: session, update: updateSession } = useSession();
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);

  // Form state
  const [ibAccountId, setIbAccountId] = useState('');
  const [ibTradingMode, setIbTradingMode] = useState<'paper' | 'live'>('paper');
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system');
  const [timezone, setTimezone] = useState('America/New_York');
  const [defaultAnalysisType, setDefaultAnalysisType] = useState('stock');
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);

  const handleNext = async () => {
    if (currentStep === STEPS.length - 2) {
      // Save and complete onboarding
      await completeOnboarding();
    } else {
      setCurrentStep((prev) => Math.min(prev + 1, STEPS.length - 1));
    }
  };

  const handleBack = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 0));
  };

  const completeOnboarding = async () => {
    try {
      setLoading(true);

      // Save IB settings if provided
      if (ibAccountId) {
        await api.user.updateIbAccount({
          ib_account_id: ibAccountId,
          ib_trading_mode: ibTradingMode,
          ib_gateway_port: null,
        });
      }

      // Save preferences
      await api.user.updateProfile({
        timezone,
        theme,
        notifications_enabled: notificationsEnabled,
        default_analysis_type: defaultAnalysisType,
      });

      // Mark onboarding complete
      await api.auth.completeOnboarding();

      // Update session
      await updateSession();

      // Move to complete step
      setCurrentStep(STEPS.length - 1);
    } catch (error) {
      console.error('Failed to complete onboarding:', error);
    } finally {
      setLoading(false);
    }
  };

  const goToDashboard = () => {
    router.push('/');
  };

  const renderStepContent = () => {
    const step = STEPS[currentStep];

    switch (step.id) {
      case 'welcome':
        return (
          <div className="text-center space-y-6">
            <div className="text-6xl">🚀</div>
            <h2 className="text-2xl font-bold">Welcome to Tradegent!</h2>
            <p className="text-muted-foreground max-w-md mx-auto">
              Let's get you set up with your trading environment. This will only take a minute.
            </p>
            <div className="pt-4">
              <p className="text-sm text-muted-foreground">
                Logged in as <span className="font-medium">{session?.user?.email}</span>
              </p>
            </div>
          </div>
        );

      case 'ib-account':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h2 className="text-xl font-bold">Interactive Brokers Account</h2>
              <p className="text-muted-foreground mt-2">
                Connect your IB account for trading (optional)
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">IB Account ID</label>
                <Input
                  value={ibAccountId}
                  onChange={(e) => setIbAccountId(e.target.value)}
                  className="mt-1"
                  placeholder="e.g., DU1234567"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  You can skip this and configure it later in Settings
                </p>
              </div>

              <div>
                <label className="text-sm font-medium">Trading Mode</label>
                <div className="mt-2 grid grid-cols-2 gap-4">
                  <button
                    onClick={() => setIbTradingMode('paper')}
                    className={cn(
                      'flex items-center gap-3 p-4 rounded-lg border transition-colors',
                      ibTradingMode === 'paper'
                        ? 'border-primary bg-primary/5'
                        : 'hover:border-primary/50'
                    )}
                  >
                    <span className="text-2xl">📋</span>
                    <div className="text-left">
                      <p className="font-medium">Paper Trading</p>
                      <p className="text-xs text-muted-foreground">Simulated, no real money</p>
                    </div>
                  </button>
                  <button
                    onClick={() => setIbTradingMode('live')}
                    className={cn(
                      'flex items-center gap-3 p-4 rounded-lg border transition-colors',
                      ibTradingMode === 'live'
                        ? 'border-loss bg-loss/5'
                        : 'hover:border-primary/50'
                    )}
                  >
                    <span className="text-2xl">💰</span>
                    <div className="text-left">
                      <p className="font-medium">Live Trading</p>
                      <p className="text-xs text-muted-foreground">Real money</p>
                    </div>
                  </button>
                </div>
                {ibTradingMode === 'live' && (
                  <div className="mt-2 p-3 bg-loss/10 border border-loss/20 rounded-lg flex items-start gap-2">
                    <AlertTriangle className="h-5 w-5 text-loss flex-shrink-0" />
                    <p className="text-sm text-loss">
                      Live trading uses real money. We recommend starting with paper trading.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        );

      case 'preferences':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h2 className="text-xl font-bold">Your Preferences</h2>
              <p className="text-muted-foreground mt-2">
                Customize your trading experience
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">Theme</label>
                <div className="mt-2 grid grid-cols-3 gap-4">
                  {(['light', 'dark', 'system'] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setTheme(t)}
                      className={cn(
                        'flex flex-col items-center gap-2 p-4 rounded-lg border transition-colors',
                        theme === t
                          ? 'border-primary bg-primary/5'
                          : 'hover:border-primary/50'
                      )}
                    >
                      <div
                        className={cn(
                          'h-8 w-8 rounded-lg',
                          t === 'light'
                            ? 'bg-white border'
                            : t === 'dark'
                            ? 'bg-gray-900'
                            : 'bg-gradient-to-br from-white to-gray-900'
                        )}
                      />
                      <span className="text-sm capitalize">{t}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium">Timezone</label>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="mt-1 w-full p-2 border rounded-md bg-background"
                >
                  <option value="America/New_York">Eastern Time (ET)</option>
                  <option value="America/Chicago">Central Time (CT)</option>
                  <option value="America/Denver">Mountain Time (MT)</option>
                  <option value="America/Los_Angeles">Pacific Time (PT)</option>
                  <option value="UTC">UTC</option>
                </select>
              </div>

              <div>
                <label className="text-sm font-medium">Default Analysis Type</label>
                <div className="mt-2 grid grid-cols-2 gap-4">
                  <button
                    onClick={() => setDefaultAnalysisType('stock')}
                    className={cn(
                      'p-4 rounded-lg border transition-colors text-left',
                      defaultAnalysisType === 'stock'
                        ? 'border-primary bg-primary/5'
                        : 'hover:border-primary/50'
                    )}
                  >
                    <p className="font-medium">Stock Analysis</p>
                    <p className="text-xs text-muted-foreground">Technical & fundamental</p>
                  </button>
                  <button
                    onClick={() => setDefaultAnalysisType('earnings')}
                    className={cn(
                      'p-4 rounded-lg border transition-colors text-left',
                      defaultAnalysisType === 'earnings'
                        ? 'border-primary bg-primary/5'
                        : 'hover:border-primary/50'
                    )}
                  >
                    <p className="font-medium">Earnings Analysis</p>
                    <p className="text-xs text-muted-foreground">Pre-earnings plays</p>
                  </button>
                </div>
              </div>
            </div>
          </div>
        );

      case 'notifications':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h2 className="text-xl font-bold">Notifications</h2>
              <p className="text-muted-foreground mt-2">
                Stay informed about your trades
              </p>
            </div>

            <div className="space-y-4">
              <div
                className={cn(
                  'p-4 rounded-lg border cursor-pointer transition-colors',
                  notificationsEnabled
                    ? 'border-primary bg-primary/5'
                    : 'hover:border-primary/50'
                )}
                onClick={() => setNotificationsEnabled(!notificationsEnabled)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Bell className="h-5 w-5" />
                    <div>
                      <p className="font-medium">Enable Notifications</p>
                      <p className="text-sm text-muted-foreground">
                        Get alerts for watchlist triggers, analysis completion, and more
                      </p>
                    </div>
                  </div>
                  <div
                    className={cn(
                      'w-12 h-6 rounded-full transition-colors',
                      notificationsEnabled ? 'bg-primary' : 'bg-muted'
                    )}
                  >
                    <div
                      className={cn(
                        'w-5 h-5 bg-white rounded-full m-0.5 transition-transform',
                        notificationsEnabled && 'translate-x-6'
                      )}
                    />
                  </div>
                </div>
              </div>

              {notificationsEnabled && (
                <div className="p-4 bg-muted/50 rounded-lg space-y-2 text-sm">
                  <p className="font-medium">You'll receive notifications for:</p>
                  <ul className="list-disc list-inside text-muted-foreground space-y-1">
                    <li>Watchlist entry triggers</li>
                    <li>Analysis completion</li>
                    <li>Position updates</li>
                    <li>Earnings reminders</li>
                  </ul>
                </div>
              )}
            </div>
          </div>
        );

      case 'complete':
        return (
          <div className="text-center space-y-6">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gain/10">
              <CheckCircle2 className="h-10 w-10 text-gain" />
            </div>
            <h2 className="text-2xl font-bold">You're all set!</h2>
            <p className="text-muted-foreground max-w-md mx-auto">
              Your trading environment is configured. You can change any of these settings later.
            </p>
            <div className="pt-4">
              <Button size="lg" onClick={goToDashboard}>
                Go to Dashboard
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-muted/30">
      <Card className="w-full max-w-2xl">
        {/* Progress Steps */}
        <CardHeader className="border-b">
          <div className="flex items-center justify-between">
            {STEPS.map((step, index) => {
              const Icon = step.icon;
              const isActive = index === currentStep;
              const isComplete = index < currentStep;

              return (
                <div key={step.id} className="flex items-center">
                  <div className="flex flex-col items-center gap-1">
                    <div
                      className={cn(
                        'w-10 h-10 rounded-full flex items-center justify-center transition-colors',
                        isActive
                          ? 'bg-primary text-primary-foreground'
                          : isComplete
                          ? 'bg-gain text-white'
                          : 'bg-muted text-muted-foreground'
                      )}
                    >
                      {isComplete ? (
                        <CheckCircle2 className="h-5 w-5" />
                      ) : (
                        <Icon className="h-5 w-5" />
                      )}
                    </div>
                    <span
                      className={cn(
                        'text-xs font-medium',
                        isActive
                          ? 'text-primary'
                          : isComplete
                          ? 'text-gain'
                          : 'text-muted-foreground'
                      )}
                    >
                      {step.title}
                    </span>
                  </div>
                  {index < STEPS.length - 1 && (
                    <div
                      className={cn(
                        'w-12 h-0.5 mx-2',
                        index < currentStep ? 'bg-gain' : 'bg-muted'
                      )}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </CardHeader>

        <CardContent className="p-8">
          {renderStepContent()}
        </CardContent>

        {/* Navigation */}
        {currentStep < STEPS.length - 1 && (
          <div className="px-8 pb-8 flex justify-between">
            <Button
              variant="outline"
              onClick={handleBack}
              disabled={currentStep === 0}
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            <Button onClick={handleNext} disabled={loading}>
              {loading ? (
                'Saving...'
              ) : currentStep === STEPS.length - 2 ? (
                'Complete Setup'
              ) : (
                <>
                  Next
                  <ChevronRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

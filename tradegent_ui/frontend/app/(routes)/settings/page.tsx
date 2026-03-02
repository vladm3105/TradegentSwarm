'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Settings,
  Server,
  Palette,
  Bell,
  Database,
  CheckCircle2,
  XCircle,
  RefreshCw,
  User,
  Key,
  Briefcase,
  Trash2,
  Copy,
  Plus,
  Eye,
  EyeOff,
  AlertTriangle,
  Shield,
  ExternalLink,
} from 'lucide-react';
import { useUIStore } from '@/stores/ui-store';
import { cn } from '@/lib/utils';
import { mockServices } from '@/lib/mock-data';
import { api } from '@/lib/api';

interface IBAccountSettings {
  ib_account_id: string | null;
  ib_trading_mode: 'paper' | 'live';
  ib_gateway_port: number | null;
}

interface ApiKey {
  id: number;
  key_prefix: string;
  name: string;
  permissions: string[];
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
}

interface Auth0Config {
  auth0_domain: string;
  auth0_client_id: string;
  auth0_client_secret_masked: string;
  auth0_audience: string;
  is_configured: boolean;
}

export default function SettingsPage() {
  const { data: session } = useSession();
  const { theme, setTheme } = useUIStore();
  const [activeTab, setActiveTab] = useState('general');

  // Profile state
  const [profileName, setProfileName] = useState('');
  const [profileTimezone, setProfileTimezone] = useState('America/New_York');
  const [profileSaving, setProfileSaving] = useState(false);

  // IB Account state
  const [ibSettings, setIbSettings] = useState<IBAccountSettings>({
    ib_account_id: null,
    ib_trading_mode: 'paper',
    ib_gateway_port: null,
  });
  const [ibAccountId, setIbAccountId] = useState('');
  const [ibTradingMode, setIbTradingMode] = useState<'paper' | 'live'>('paper');
  const [ibGatewayPort, setIbGatewayPort] = useState('');
  const [ibSaving, setIbSaving] = useState(false);
  const [ibLoading, setIbLoading] = useState(true);

  // API Keys state
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(true);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyExpires, setNewKeyExpires] = useState('');
  const [creatingKey, setCreatingKey] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [showNewKey, setShowNewKey] = useState(false);

  // Auth0 Configuration state (admin only)
  const [auth0Config, setAuth0Config] = useState<Auth0Config | null>(null);
  const [auth0Loading, setAuth0Loading] = useState(false);
  const [auth0Saving, setAuth0Saving] = useState(false);
  const [auth0Domain, setAuth0Domain] = useState('');
  const [auth0ClientId, setAuth0ClientId] = useState('');
  const [auth0ClientSecret, setAuth0ClientSecret] = useState('');
  const [auth0Audience, setAuth0Audience] = useState('https://tradegent-api.local');
  const [showAuth0Secret, setShowAuth0Secret] = useState(false);
  const [auth0Error, setAuth0Error] = useState<string | null>(null);
  const [auth0Success, setAuth0Success] = useState<string | null>(null);
  const [restartRequested, setRestartRequested] = useState(false);

  // Check if user is admin
  const isAdmin = (session?.user as any)?.roles?.includes('admin') || false;

  // Load IB settings
  useEffect(() => {
    if (session) {
      loadIbSettings();
      loadApiKeys();
      // Set profile name from session
      setProfileName(session.user?.name || '');

      // Load Auth0 config if admin
      if (isAdmin) {
        loadAuth0Config();
      }
    }
  }, [session, isAdmin]);

  const loadIbSettings = async () => {
    try {
      setIbLoading(true);
      const settings = await api.user.getIbAccount();
      setIbSettings(settings);
      setIbAccountId(settings.ib_account_id || '');
      setIbTradingMode(settings.ib_trading_mode || 'paper');
      setIbGatewayPort(settings.ib_gateway_port?.toString() || '');
    } catch (error) {
      console.error('Failed to load IB settings:', error);
    } finally {
      setIbLoading(false);
    }
  };

  const saveIbSettings = async () => {
    try {
      setIbSaving(true);
      await api.user.updateIbAccount({
        ib_account_id: ibAccountId,
        ib_trading_mode: ibTradingMode,
        ib_gateway_port: ibGatewayPort ? parseInt(ibGatewayPort) : null,
      });
      await loadIbSettings();
    } catch (error) {
      console.error('Failed to save IB settings:', error);
    } finally {
      setIbSaving(false);
    }
  };

  const loadApiKeys = async () => {
    try {
      setApiKeysLoading(true);
      const keys = await api.apiKeys.list();
      setApiKeys(keys);
    } catch (error) {
      console.error('Failed to load API keys:', error);
    } finally {
      setApiKeysLoading(false);
    }
  };

  const loadAuth0Config = async () => {
    try {
      setAuth0Loading(true);
      setAuth0Error(null);
      const config = await api.settings.getAuth0();
      setAuth0Config(config);
      setAuth0Domain(config.auth0_domain || '');
      setAuth0ClientId(config.auth0_client_id || '');
      setAuth0Audience(config.auth0_audience || 'https://tradegent-api.local');
      // Don't set client secret from server (it's masked)
    } catch (error) {
      console.error('Failed to load Auth0 config:', error);
      setAuth0Error('Failed to load Auth0 configuration');
    } finally {
      setAuth0Loading(false);
    }
  };

  const saveAuth0Config = async () => {
    // Validation
    if (!auth0Domain.trim()) {
      setAuth0Error('Auth0 domain is required');
      return;
    }
    if (!auth0Domain.includes('.')) {
      setAuth0Error('Invalid Auth0 domain format (e.g., your-tenant.auth0.com)');
      return;
    }
    if (!auth0ClientId.trim()) {
      setAuth0Error('Client ID is required');
      return;
    }
    if (!auth0ClientSecret.trim()) {
      setAuth0Error('Client Secret is required');
      return;
    }

    try {
      setAuth0Saving(true);
      setAuth0Error(null);
      setAuth0Success(null);

      await api.settings.updateAuth0({
        auth0_domain: auth0Domain,
        auth0_client_id: auth0ClientId,
        auth0_client_secret: auth0ClientSecret,
        auth0_audience: auth0Audience || 'https://tradegent-api.local',
      });

      setAuth0Success('Auth0 configuration saved successfully. A server restart is required for changes to take effect.');
      setAuth0ClientSecret(''); // Clear secret after save
      await loadAuth0Config();
    } catch (error) {
      console.error('Failed to save Auth0 config:', error);
      setAuth0Error('Failed to save Auth0 configuration');
    } finally {
      setAuth0Saving(false);
    }
  };

  const requestRestart = async () => {
    try {
      await api.settings.requestRestart();
      setRestartRequested(true);
      setAuth0Success('Server restart requested. Please wait for the server to restart.');
    } catch (error) {
      console.error('Failed to request restart:', error);
      setAuth0Error('Failed to request server restart');
    }
  };

  const createApiKey = async () => {
    if (!newKeyName.trim()) return;

    try {
      setCreatingKey(true);
      const response = await api.apiKeys.create({
        name: newKeyName,
        expires_in_days: newKeyExpires ? parseInt(newKeyExpires) : null,
      });
      setNewlyCreatedKey(response.key);
      setShowNewKey(true);
      setNewKeyName('');
      setNewKeyExpires('');
      await loadApiKeys();
    } catch (error) {
      console.error('Failed to create API key:', error);
    } finally {
      setCreatingKey(false);
    }
  };

  const revokeApiKey = async (keyId: number) => {
    if (!confirm('Are you sure you want to revoke this API key?')) return;

    try {
      await api.apiKeys.revoke(keyId);
      await loadApiKeys();
    } catch (error) {
      console.error('Failed to revoke API key:', error);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const saveProfile = async () => {
    try {
      setProfileSaving(true);
      await api.user.updateProfile({
        name: profileName,
        timezone: profileTimezone,
      });
    } catch (error) {
      console.error('Failed to save profile:', error);
    } finally {
      setProfileSaving(false);
    }
  };

  return (
    <div className="flex-1 space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Configure your trading dashboard
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="general">
            <Settings className="h-4 w-4 mr-2" />
            General
          </TabsTrigger>
          <TabsTrigger value="profile">
            <User className="h-4 w-4 mr-2" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="ib-account">
            <Briefcase className="h-4 w-4 mr-2" />
            IB Account
          </TabsTrigger>
          <TabsTrigger value="api-keys">
            <Key className="h-4 w-4 mr-2" />
            API Keys
          </TabsTrigger>
          {isAdmin && (
            <TabsTrigger value="auth0">
              <Shield className="h-4 w-4 mr-2" />
              Auth0
            </TabsTrigger>
          )}
          <TabsTrigger value="appearance">
            <Palette className="h-4 w-4 mr-2" />
            Appearance
          </TabsTrigger>
          <TabsTrigger value="services">
            <Server className="h-4 w-4 mr-2" />
            Services
          </TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="h-4 w-4 mr-2" />
            Notifications
          </TabsTrigger>
        </TabsList>

        {/* General Tab */}
        <TabsContent value="general" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>API Configuration</CardTitle>
              <CardDescription>
                Configure backend API endpoints
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium">Backend URL</label>
                <Input
                  defaultValue="http://localhost:8081"
                  className="mt-1"
                  disabled
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Set via NEXT_PUBLIC_API_URL environment variable
                </p>
              </div>
              <div>
                <label className="text-sm font-medium">WebSocket URL</label>
                <Input
                  defaultValue="ws://localhost:8081/ws/agent"
                  className="mt-1"
                  disabled
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Trading Settings</CardTitle>
              <CardDescription>
                Configure trading behavior
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Auto-Execute Trades</p>
                  <p className="text-sm text-muted-foreground">
                    Automatically execute trades when gate passes
                  </p>
                </div>
                <Badge variant="outline" className="text-yellow-500">
                  Disabled
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Paper Trading Mode</p>
                  <p className="text-sm text-muted-foreground">
                    Use paper trading account
                  </p>
                </div>
                <Badge variant="outline" className="text-gain">
                  Enabled
                </Badge>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Profile Tab */}
        <TabsContent value="profile" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>
                Manage your account details
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium">Email</label>
                <Input
                  value={session?.user?.email || ''}
                  className="mt-1"
                  disabled
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Email is managed by Auth0
                </p>
              </div>
              <div>
                <label className="text-sm font-medium">Name</label>
                <Input
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  className="mt-1"
                  placeholder="Your name"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Timezone</label>
                <select
                  value={profileTimezone}
                  onChange={(e) => setProfileTimezone(e.target.value)}
                  className="mt-1 w-full p-2 border rounded-md bg-background"
                >
                  <option value="America/New_York">Eastern Time (ET)</option>
                  <option value="America/Chicago">Central Time (CT)</option>
                  <option value="America/Denver">Mountain Time (MT)</option>
                  <option value="America/Los_Angeles">Pacific Time (PT)</option>
                  <option value="UTC">UTC</option>
                </select>
              </div>
              <Button onClick={saveProfile} disabled={profileSaving}>
                {profileSaving ? 'Saving...' : 'Save Profile'}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Roles & Permissions</CardTitle>
              <CardDescription>
                Your account access level
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium mb-2">Roles</p>
                <div className="flex gap-2">
                  {(session?.user as any)?.roles?.map((role: string) => (
                    <Badge key={role} variant="secondary">{role}</Badge>
                  )) || <Badge variant="outline">No roles assigned</Badge>}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* IB Account Tab */}
        <TabsContent value="ib-account" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Briefcase className="h-5 w-5" />
                Interactive Brokers Account
              </CardTitle>
              <CardDescription>
                Configure your IB Gateway connection for trading
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {ibLoading ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <>
                  <div>
                    <label className="text-sm font-medium">IB Account ID</label>
                    <Input
                      value={ibAccountId}
                      onChange={(e) => setIbAccountId(e.target.value)}
                      className="mt-1"
                      placeholder="e.g., DU1234567"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Your Interactive Brokers account ID (paper or live)
                    </p>
                  </div>

                  <div>
                    <label className="text-sm font-medium">Trading Mode</label>
                    <div className="mt-2 flex gap-4">
                      <button
                        onClick={() => setIbTradingMode('paper')}
                        className={cn(
                          'flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors',
                          ibTradingMode === 'paper'
                            ? 'border-primary bg-primary/5 text-primary'
                            : 'hover:border-primary/50'
                        )}
                      >
                        <span className="text-lg">📋</span>
                        <div className="text-left">
                          <p className="font-medium">Paper Trading</p>
                          <p className="text-xs text-muted-foreground">Simulated trading</p>
                        </div>
                      </button>
                      <button
                        onClick={() => setIbTradingMode('live')}
                        className={cn(
                          'flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors',
                          ibTradingMode === 'live'
                            ? 'border-loss bg-loss/5 text-loss'
                            : 'hover:border-primary/50'
                        )}
                      >
                        <span className="text-lg">💰</span>
                        <div className="text-left">
                          <p className="font-medium">Live Trading</p>
                          <p className="text-xs text-muted-foreground">Real money</p>
                        </div>
                      </button>
                    </div>
                    {ibTradingMode === 'live' && (
                      <div className="mt-2 p-3 bg-loss/10 border border-loss/20 rounded-lg flex items-start gap-2">
                        <AlertTriangle className="h-5 w-5 text-loss flex-shrink-0 mt-0.5" />
                        <p className="text-sm text-loss">
                          Live trading uses real money. Make sure you understand the risks.
                        </p>
                      </div>
                    )}
                  </div>

                  <div>
                    <label className="text-sm font-medium">Gateway Port (Optional)</label>
                    <Input
                      value={ibGatewayPort}
                      onChange={(e) => setIbGatewayPort(e.target.value)}
                      className="mt-1"
                      placeholder="e.g., 4002"
                      type="number"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Custom port for IB Gateway (default: 4002 for paper, 4001 for live)
                    </p>
                  </div>

                  <Button onClick={saveIbSettings} disabled={ibSaving}>
                    {ibSaving ? 'Saving...' : 'Save IB Settings'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Connection Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                {ibSettings.ib_account_id ? (
                  <>
                    <CheckCircle2 className="h-5 w-5 text-gain" />
                    <div>
                      <p className="font-medium">Account Configured</p>
                      <p className="text-sm text-muted-foreground">
                        {ibSettings.ib_account_id} ({ibSettings.ib_trading_mode})
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <XCircle className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">No Account Configured</p>
                      <p className="text-sm text-muted-foreground">
                        Enter your IB account details above
                      </p>
                    </div>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* API Keys Tab */}
        <TabsContent value="api-keys" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                API Keys
              </CardTitle>
              <CardDescription>
                Create API keys for programmatic access (CLI, automation)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* New Key Form */}
              <div className="p-4 border rounded-lg space-y-4">
                <h3 className="font-medium">Create New API Key</h3>
                <div className="flex gap-4">
                  <div className="flex-1">
                    <Input
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      placeholder="Key name (e.g., CLI, Trading Bot)"
                    />
                  </div>
                  <div className="w-40">
                    <Input
                      value={newKeyExpires}
                      onChange={(e) => setNewKeyExpires(e.target.value)}
                      placeholder="Expires (days)"
                      type="number"
                    />
                  </div>
                  <Button onClick={createApiKey} disabled={creatingKey || !newKeyName.trim()}>
                    <Plus className="h-4 w-4 mr-2" />
                    Create
                  </Button>
                </div>
              </div>

              {/* Newly Created Key Warning */}
              {newlyCreatedKey && (
                <div className="p-4 bg-gain/10 border border-gain/20 rounded-lg space-y-2">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-gain" />
                    <p className="font-medium text-gain">New API Key Created</p>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Copy this key now. You won't be able to see it again.
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 p-2 bg-background border rounded font-mono text-sm">
                      {showNewKey ? newlyCreatedKey : '••••••••••••••••••••••••••••••••'}
                    </code>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowNewKey(!showNewKey)}
                    >
                      {showNewKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyToClipboard(newlyCreatedKey)}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setNewlyCreatedKey(null)}
                  >
                    Dismiss
                  </Button>
                </div>
              )}

              {/* Existing Keys */}
              {apiKeysLoading ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : apiKeys.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Key className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No API keys yet</p>
                  <p className="text-sm">Create one above for programmatic access</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {apiKeys.map((key) => (
                    <div
                      key={key.id}
                      className="flex items-center justify-between p-3 rounded-lg border"
                    >
                      <div className="flex items-center gap-3">
                        <Key className="h-5 w-5 text-muted-foreground" />
                        <div>
                          <p className="font-medium">{key.name}</p>
                          <p className="text-xs text-muted-foreground font-mono">
                            tg_{key.key_prefix}...
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right text-sm">
                          {key.last_used_at ? (
                            <p className="text-muted-foreground">
                              Last used: {new Date(key.last_used_at).toLocaleDateString()}
                            </p>
                          ) : (
                            <p className="text-muted-foreground">Never used</p>
                          )}
                          {key.expires_at && (
                            <p className="text-xs">
                              Expires: {new Date(key.expires_at).toLocaleDateString()}
                            </p>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => revokeApiKey(key.id)}
                          className="text-loss hover:text-loss"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Auth0 Configuration Tab (Admin Only) */}
        {isAdmin && (
          <TabsContent value="auth0" className="mt-6 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  Auth0 Configuration
                </CardTitle>
                <CardDescription>
                  Configure Auth0 for user authentication. Changes require a server restart.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {auth0Loading ? (
                  <div className="flex items-center justify-center py-8">
                    <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                  <>
                    {/* Status Badge */}
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">Status:</span>
                      {auth0Config?.is_configured ? (
                        <Badge variant="outline" className="text-gain">
                          <CheckCircle2 className="h-3 w-3 mr-1" />
                          Configured
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-muted-foreground">
                          <XCircle className="h-3 w-3 mr-1" />
                          Not Configured
                        </Badge>
                      )}
                    </div>

                    {/* Error/Success Messages */}
                    {auth0Error && (
                      <div className="p-3 bg-loss/10 border border-loss/20 rounded-lg flex items-start gap-2">
                        <AlertTriangle className="h-5 w-5 text-loss flex-shrink-0 mt-0.5" />
                        <p className="text-sm text-loss">{auth0Error}</p>
                      </div>
                    )}
                    {auth0Success && (
                      <div className="p-3 bg-gain/10 border border-gain/20 rounded-lg flex items-start gap-2">
                        <CheckCircle2 className="h-5 w-5 text-gain flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="text-sm text-gain">{auth0Success}</p>
                          {!restartRequested && auth0Success.includes('restart') && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="mt-2"
                              onClick={requestRestart}
                            >
                              <RefreshCw className="h-4 w-4 mr-2" />
                              Request Server Restart
                            </Button>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Auth0 Documentation Link */}
                    <div className="p-4 bg-muted/50 rounded-lg">
                      <div className="flex items-start gap-3">
                        <ExternalLink className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm font-medium">New to Auth0?</p>
                          <p className="text-sm text-muted-foreground mb-2">
                            Create an Auth0 tenant and application to enable social login (Google, GitHub) and email/password authentication.
                          </p>
                          <a
                            href="https://auth0.com/signup"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-primary hover:underline flex items-center gap-1"
                          >
                            Create Auth0 Account
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </div>
                      </div>
                    </div>

                    {/* Configuration Form */}
                    <div className="space-y-4">
                      <div>
                        <label className="text-sm font-medium">Auth0 Domain</label>
                        <Input
                          value={auth0Domain}
                          onChange={(e) => setAuth0Domain(e.target.value)}
                          className="mt-1"
                          placeholder="your-tenant.auth0.com"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          Your Auth0 tenant domain (e.g., your-tenant.auth0.com)
                        </p>
                      </div>

                      <div>
                        <label className="text-sm font-medium">Client ID</label>
                        <Input
                          value={auth0ClientId}
                          onChange={(e) => setAuth0ClientId(e.target.value)}
                          className="mt-1"
                          placeholder="Your Auth0 Application Client ID"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          Found in Auth0 Dashboard → Applications → Your App → Settings
                        </p>
                      </div>

                      <div>
                        <label className="text-sm font-medium">Client Secret</label>
                        <div className="flex gap-2 mt-1">
                          <Input
                            type={showAuth0Secret ? 'text' : 'password'}
                            value={auth0ClientSecret}
                            onChange={(e) => setAuth0ClientSecret(e.target.value)}
                            placeholder={auth0Config?.auth0_client_secret_masked || 'Enter your Client Secret'}
                            className="flex-1"
                          />
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setShowAuth0Secret(!showAuth0Secret)}
                          >
                            {showAuth0Secret ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {auth0Config?.is_configured
                            ? 'Enter a new secret to update, or leave blank to keep current'
                            : 'Found in Auth0 Dashboard → Applications → Your App → Settings'}
                        </p>
                      </div>

                      <div>
                        <label className="text-sm font-medium">API Audience</label>
                        <Input
                          value={auth0Audience}
                          onChange={(e) => setAuth0Audience(e.target.value)}
                          className="mt-1"
                          placeholder="https://tradegent-api.local"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          The API identifier in Auth0 (create under APIs in dashboard)
                        </p>
                      </div>
                    </div>

                    {/* Callback URLs Info */}
                    <div className="p-4 border rounded-lg space-y-3">
                      <h4 className="font-medium text-sm">Configure in Auth0 Dashboard</h4>
                      <div className="space-y-2 text-sm">
                        <div>
                          <p className="text-muted-foreground">Allowed Callback URLs:</p>
                          <code className="text-xs bg-muted px-2 py-1 rounded">
                            {typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3001'}/api/auth/callback/auth0
                          </code>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Allowed Logout URLs:</p>
                          <code className="text-xs bg-muted px-2 py-1 rounded">
                            {typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3001'}
                          </code>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Allowed Web Origins:</p>
                          <code className="text-xs bg-muted px-2 py-1 rounded">
                            {typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3001'}
                          </code>
                        </div>
                      </div>
                    </div>

                    {/* Save Button */}
                    <div className="flex gap-3">
                      <Button
                        onClick={saveAuth0Config}
                        disabled={auth0Saving || (!auth0Domain && !auth0ClientId)}
                      >
                        {auth0Saving ? (
                          <>
                            <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          'Save Auth0 Configuration'
                        )}
                      </Button>
                      <Button variant="outline" onClick={loadAuth0Config}>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Refresh
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Auth0 Features Info */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Authentication Features</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-gain flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">Social Login</p>
                      <p className="text-sm text-muted-foreground">
                        Google, GitHub, and other OAuth providers
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-gain flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">Email/Password</p>
                      <p className="text-sm text-muted-foreground">
                        Traditional email and password authentication
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-gain flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">Multi-Factor Auth</p>
                      <p className="text-sm text-muted-foreground">
                        SMS, TOTP, and WebAuthn support
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-gain flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">JWT Tokens</p>
                      <p className="text-sm text-muted-foreground">
                        RS256 signed tokens with roles and permissions
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Appearance Tab */}
        <TabsContent value="appearance" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Theme</CardTitle>
              <CardDescription>
                Choose your preferred color scheme
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
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
                        'h-12 w-12 rounded-lg',
                        t === 'light'
                          ? 'bg-white border'
                          : t === 'dark'
                          ? 'bg-gray-900'
                          : 'bg-gradient-to-br from-white to-gray-900'
                      )}
                    />
                    <span className="text-sm font-medium capitalize">{t}</span>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Display Options</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Compact Mode</p>
                  <p className="text-sm text-muted-foreground">
                    Reduce spacing for more content
                  </p>
                </div>
                <Badge variant="outline">Off</Badge>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Show P&L Colors</p>
                  <p className="text-sm text-muted-foreground">
                    Green/red for gains/losses
                  </p>
                </div>
                <Badge variant="outline" className="text-gain">On</Badge>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Services Tab */}
        <TabsContent value="services" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Service Status</CardTitle>
                  <CardDescription>
                    Monitor backend services and connections
                  </CardDescription>
                </div>
                <Button variant="outline" size="sm">
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {mockServices.map((service) => (
                  <div
                    key={service.name}
                    className="flex items-center justify-between p-3 rounded-lg border"
                  >
                    <div className="flex items-center gap-3">
                      {service.status === 'healthy' ? (
                        <CheckCircle2 className="h-5 w-5 text-gain" />
                      ) : (
                        <XCircle className="h-5 w-5 text-loss" />
                      )}
                      <div>
                        <p className="font-medium">{service.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {service.url}
                        </p>
                      </div>
                    </div>
                    <Badge
                      variant="outline"
                      className={
                        service.status === 'healthy'
                          ? 'text-gain'
                          : 'text-loss'
                      }
                    >
                      {service.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Database Info
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">PostgreSQL</p>
                  <p className="font-mono">tradegent@localhost:5433</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Neo4j</p>
                  <p className="font-mono">bolt://localhost:7688</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notifications Tab */}
        <TabsContent value="notifications" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
              <CardDescription>
                Configure alerts and notifications
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Watchlist Triggers</p>
                  <p className="text-sm text-muted-foreground">
                    Notify when watchlist conditions are met
                  </p>
                </div>
                <Badge variant="outline" className="text-gain">On</Badge>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Analysis Complete</p>
                  <p className="text-sm text-muted-foreground">
                    Notify when analysis finishes
                  </p>
                </div>
                <Badge variant="outline" className="text-gain">On</Badge>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Position Updates</p>
                  <p className="text-sm text-muted-foreground">
                    Notify on position changes
                  </p>
                </div>
                <Badge variant="outline">Off</Badge>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

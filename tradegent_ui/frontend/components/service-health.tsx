'use client';

import { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Server, AlertCircle, CheckCircle, XCircle } from 'lucide-react';
import { createLogger } from '@/lib/logger';

const log = createLogger('service-health');

interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  mcp_servers: {
    ib_mcp: boolean;
    trading_rag: boolean;
    trading_graph: boolean;
  };
}

export function ServiceHealth() {
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function checkHealth() {
      try {
        const response = await fetch('/api/orchestrator?path=%2Fhealth');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        setHealth(data);
        setError(null);
      } catch (e) {
        log.error('Health check failed', { error: String(e) });
        setError('Connection failed');
        setHealth(null);
      } finally {
        setLoading(false);
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30 seconds

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Badge variant="secondary" className="animate-pulse">
        <Server className="h-3 w-3 mr-1" />
        Checking...
      </Badge>
    );
  }

  if (error || !health) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="destructive">
              <XCircle className="h-3 w-3 mr-1" />
              Offline
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            <p>Cannot connect to backend</p>
            {error && <p className="text-xs text-muted-foreground">{error}</p>}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  const isHealthy = health.status === 'healthy';
  const isDegraded = health.status === 'degraded';

  const serviceCount = Object.values(health.mcp_servers).filter(Boolean).length;
  const totalServices = Object.keys(health.mcp_servers).length;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant={isHealthy ? 'default' : isDegraded ? 'secondary' : 'destructive'}
            className={isHealthy ? 'bg-green-500 hover:bg-green-600' : ''}
          >
            {isHealthy ? (
              <CheckCircle className="h-3 w-3 mr-1" />
            ) : isDegraded ? (
              <AlertCircle className="h-3 w-3 mr-1" />
            ) : (
              <XCircle className="h-3 w-3 mr-1" />
            )}
            {serviceCount}/{totalServices} Services
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <div className="space-y-2">
            <p className="font-medium">Backend Services</p>
            <div className="space-y-1 text-xs">
              <ServiceRow
                name="IB Gateway"
                connected={health.mcp_servers.ib_mcp}
              />
              <ServiceRow
                name="RAG Service"
                connected={health.mcp_servers.trading_rag}
              />
              <ServiceRow
                name="Graph Service"
                connected={health.mcp_servers.trading_graph}
              />
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function ServiceRow({ name, connected }: { name: string; connected: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{name}</span>
      {connected ? (
        <CheckCircle className="h-3 w-3 text-green-500" />
      ) : (
        <XCircle className="h-3 w-3 text-red-500" />
      )}
    </div>
  );
}

'use client';

import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useChatStore } from '@/stores/chat-store';

interface ConnectionStatusProps {
  className?: string;
  showLabel?: boolean;
}

export function ConnectionStatus({
  className,
  showLabel = true,
}: ConnectionStatusProps) {
  const { isConnected, isStreaming } = useChatStore();

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-2 py-1 rounded-md text-xs font-medium',
        isConnected
          ? 'bg-gain/10 text-gain'
          : 'bg-loss/10 text-loss',
        className
      )}
    >
      {isStreaming ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : isConnected ? (
        <Wifi className="h-3 w-3" />
      ) : (
        <WifiOff className="h-3 w-3" />
      )}
      {showLabel && (
        <span>
          {isStreaming
            ? 'Streaming...'
            : isConnected
            ? 'Connected'
            : 'Disconnected'}
        </span>
      )}
    </div>
  );
}

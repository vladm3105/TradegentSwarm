'use client';

import { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Clock } from 'lucide-react';

type MarketState = 'pre-market' | 'open' | 'post-market' | 'closed';

interface MarketStatusInfo {
  state: MarketState;
  label: string;
  nextEvent: string;
  timeUntil: string;
}

function getMarketStatus(): MarketStatusInfo {
  const now = new Date();

  // Convert to Eastern Time
  const etOptions: Intl.DateTimeFormatOptions = {
    timeZone: 'America/New_York',
    hour: 'numeric',
    minute: 'numeric',
    hour12: false,
  };
  const etTime = now.toLocaleTimeString('en-US', etOptions);
  const [hours, minutes] = etTime.split(':').map(Number);
  const totalMinutes = hours * 60 + minutes;

  // Check if weekend
  const dayOfWeek = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' })).getDay();
  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;

  if (isWeekend) {
    return {
      state: 'closed',
      label: 'Weekend',
      nextEvent: 'Market opens Monday',
      timeUntil: '',
    };
  }

  // Market hours (in minutes from midnight ET)
  const PRE_MARKET_START = 4 * 60; // 4:00 AM
  const MARKET_OPEN = 9 * 60 + 30; // 9:30 AM
  const MARKET_CLOSE = 16 * 60; // 4:00 PM
  const POST_MARKET_END = 20 * 60; // 8:00 PM

  const minutesUntil = (target: number) => {
    const diff = target - totalMinutes;
    if (diff <= 0) return '';
    const h = Math.floor(diff / 60);
    const m = diff % 60;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  };

  if (totalMinutes < PRE_MARKET_START) {
    return {
      state: 'closed',
      label: 'Closed',
      nextEvent: 'Pre-market at 4:00 AM ET',
      timeUntil: minutesUntil(PRE_MARKET_START),
    };
  }

  if (totalMinutes < MARKET_OPEN) {
    return {
      state: 'pre-market',
      label: 'Pre-Market',
      nextEvent: 'Opens at 9:30 AM ET',
      timeUntil: minutesUntil(MARKET_OPEN),
    };
  }

  if (totalMinutes < MARKET_CLOSE) {
    return {
      state: 'open',
      label: 'Market Open',
      nextEvent: 'Closes at 4:00 PM ET',
      timeUntil: minutesUntil(MARKET_CLOSE),
    };
  }

  if (totalMinutes < POST_MARKET_END) {
    return {
      state: 'post-market',
      label: 'After Hours',
      nextEvent: 'Ends at 8:00 PM ET',
      timeUntil: minutesUntil(POST_MARKET_END),
    };
  }

  return {
    state: 'closed',
    label: 'Closed',
    nextEvent: 'Pre-market at 4:00 AM ET',
    timeUntil: '',
  };
}

const stateColors: Record<MarketState, string> = {
  'pre-market': 'bg-yellow-500',
  'open': 'bg-green-500',
  'post-market': 'bg-orange-500',
  'closed': 'bg-gray-500',
};

interface MarketStatusProps {
  showDetails?: boolean;
}

export function MarketStatus({ showDetails = false }: MarketStatusProps) {
  const [status, setStatus] = useState<MarketStatusInfo>(getMarketStatus);

  useEffect(() => {
    // Update every minute
    const interval = setInterval(() => {
      setStatus(getMarketStatus());
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  if (!showDetails) {
    return (
      <Badge className={`${stateColors[status.state]} text-white`}>
        {status.label}
      </Badge>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Badge className={`${stateColors[status.state]} text-white`}>
        <Clock className="h-3 w-3 mr-1" />
        {status.label}
      </Badge>
      {status.timeUntil && (
        <span className="text-xs text-muted-foreground">
          {status.nextEvent} ({status.timeUntil})
        </span>
      )}
    </div>
  );
}

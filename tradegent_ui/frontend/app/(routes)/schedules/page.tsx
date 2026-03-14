'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ScheduleManager } from '@/components/schedule-manager';
import { CalendarDays, History } from 'lucide-react';

export default function SchedulesPage() {
  return (
    <div className="flex-1 space-y-6 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Schedules</h1>
          <p className="text-muted-foreground">Manage enabled jobs and trigger runs manually.</p>
        </div>
        <Button asChild variant="outline">
          <Link href="/schedules/history">
            <History className="mr-2 h-4 w-4" />
            View History
          </Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <CalendarDays className="h-5 w-5" />
            Automation Schedules
          </CardTitle>
          <CardDescription>Toggle schedules, run them now, and inspect recent runs inline.</CardDescription>
        </CardHeader>
        <CardContent>
          <ScheduleManager />
        </CardContent>
      </Card>
    </div>
  );
}
'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  variant?: 'full' | 'card' | 'inline';
  title?: string;
  showDetails?: boolean;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    this.props.onError?.(error, errorInfo);

    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('ErrorBoundary caught an error:', error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const { variant = 'card', title = 'Something went wrong', showDetails = process.env.NODE_ENV === 'development' } = this.props;

      if (variant === 'inline') {
        return (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-loss/10 text-loss text-sm">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{title}</span>
            <Button variant="ghost" size="sm" onClick={this.handleReset} className="ml-auto">
              <RefreshCw className="h-3 w-3 mr-1" />
              Retry
            </Button>
          </div>
        );
      }

      if (variant === 'full') {
        return (
          <div className="flex min-h-screen items-center justify-center p-4">
            <Card className="max-w-lg w-full">
              <CardHeader className="text-center">
                <div className="mx-auto mb-4 h-12 w-12 rounded-full bg-loss/10 flex items-center justify-center">
                  <AlertCircle className="h-6 w-6 text-loss" />
                </div>
                <CardTitle>{title}</CardTitle>
                <CardDescription>
                  An unexpected error occurred. Please try again or return to the home page.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {showDetails && this.state.error && (
                  <div className="p-3 rounded-lg bg-muted text-xs font-mono overflow-auto max-h-32">
                    <p className="font-semibold text-loss">{this.state.error.message}</p>
                    {this.state.errorInfo?.componentStack && (
                      <pre className="mt-2 text-muted-foreground whitespace-pre-wrap">
                        {this.state.errorInfo.componentStack.slice(0, 500)}
                      </pre>
                    )}
                  </div>
                )}
                <div className="flex gap-2">
                  <Button variant="outline" className="flex-1" onClick={this.handleGoHome}>
                    <Home className="h-4 w-4 mr-2" />
                    Go Home
                  </Button>
                  <Button className="flex-1" onClick={this.handleReload}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Reload
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        );
      }

      // Default: card variant
      return (
        <Card className="border-loss/20">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-loss" />
              <CardTitle className="text-base">{title}</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {showDetails && this.state.error && (
              <div className="p-2 rounded bg-muted text-xs font-mono overflow-auto max-h-24">
                {this.state.error.message}
              </div>
            )}
            <Button variant="outline" size="sm" onClick={this.handleReset}>
              <RefreshCw className="h-3 w-3 mr-1" />
              Try Again
            </Button>
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}

// Specialized error boundaries for different areas
export function ChartErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      variant="card"
      title="Chart failed to load"
      onError={(error) => {
        // Could send to error tracking service
        console.error('Chart error:', error);
      }}
    >
      {children}
    </ErrorBoundary>
  );
}

export function WidgetErrorBoundary({ children, title = 'Widget error' }: { children: ReactNode; title?: string }) {
  return (
    <ErrorBoundary
      variant="inline"
      title={title}
    >
      {children}
    </ErrorBoundary>
  );
}

export function PageErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      variant="full"
      title="Page failed to load"
    >
      {children}
    </ErrorBoundary>
  );
}

export function ChatErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      variant="card"
      title="Chat panel error"
      onError={(error) => {
        console.error('Chat error:', error);
      }}
    >
      {children}
    </ErrorBoundary>
  );
}

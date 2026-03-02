'use client';

import { useMemo } from 'react';
import { componentRegistry } from '@/components/tradegent-components';
import { ErrorCard } from '@/components/tradegent-components';
import { validateA2UIResponse, type A2UIResponse, type A2UIComponent } from '@/types/a2ui';

interface A2UIRendererProps {
  response: A2UIResponse | unknown;
  className?: string;
}

interface RenderComponentProps {
  component: A2UIComponent;
  index: number;
}

function RenderComponent({ component, index }: RenderComponentProps) {
  const Component = componentRegistry[component.type];

  if (!Component) {
    return (
      <ErrorCard
        code="UNKNOWN_COMPONENT"
        message={`Unknown component type: ${component.type}`}
        recoverable={false}
        retry_action={null}
      />
    );
  }

  try {
    return <Component key={index} {...component.props} />;
  } catch (error) {
    return (
      <ErrorCard
        code="RENDER_ERROR"
        message={`Failed to render ${component.type}: ${String(error)}`}
        recoverable={false}
        retry_action={null}
      />
    );
  }
}

export function A2UIRenderer({ response, className }: A2UIRendererProps) {
  // Validate and parse the response
  const validatedResponse = useMemo(() => {
    if (!response) return null;

    // If already validated, use as is
    if (
      typeof response === 'object' &&
      'type' in response &&
      (response as A2UIResponse).type === 'a2ui'
    ) {
      return validateA2UIResponse(response);
    }

    // Try to parse if it's a string
    if (typeof response === 'string') {
      try {
        const parsed = JSON.parse(response);
        return validateA2UIResponse(parsed);
      } catch {
        return null;
      }
    }

    return validateA2UIResponse(response);
  }, [response]);

  if (!validatedResponse) {
    return (
      <div className={className}>
        <ErrorCard
          code="INVALID_RESPONSE"
          message="The response could not be parsed as a valid A2UI response"
          recoverable={false}
          retry_action={null}
        />
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Text response */}
      {validatedResponse.text && (
        <div className="mb-4 whitespace-pre-wrap">{validatedResponse.text}</div>
      )}

      {/* Components */}
      {validatedResponse.components.length > 0 && (
        <div className="space-y-4">
          {validatedResponse.components.map((component, index) => (
            <RenderComponent key={index} component={component} index={index} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Render a single A2UI component by type and props
 */
export function renderComponent(type: string, props: Record<string, unknown>) {
  const Component = componentRegistry[type];

  if (!Component) {
    console.warn(`Unknown A2UI component type: ${type}`);
    return null;
  }

  return <Component {...props} />;
}

/**
 * Check if a component type is supported
 */
export function isComponentSupported(type: string): boolean {
  return type in componentRegistry;
}

/**
 * Get list of all supported component types
 */
export function getSupportedComponents(): string[] {
  return Object.keys(componentRegistry);
}

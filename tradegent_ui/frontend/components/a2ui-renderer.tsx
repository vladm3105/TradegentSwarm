'use client';

import { useMemo } from 'react';
import { componentRegistry } from '@/components/tradegent-components';
import { ErrorCard } from '@/components/tradegent-components';
import { validateA2UIResponse, type A2UIResponse, type A2UIComponent } from '@/types/a2ui';
import { logger } from '@/lib/logger';

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
  const startTime = typeof performance !== 'undefined' ? performance.now() : 0;

  if (!Component) {
    logger.a2uiRender(component.type, false, 0, 'Unknown component type');
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
    const element = <Component key={index} {...component.props} />;
    const renderMs = typeof performance !== 'undefined' ? performance.now() - startTime : 0;
    logger.a2uiRender(component.type, true, renderMs);
    return element;
  } catch (error) {
    const renderMs = typeof performance !== 'undefined' ? performance.now() - startTime : 0;
    logger.a2uiRender(component.type, false, renderMs, String(error));
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
    if (!response) {
      logger.debug('A2UI renderer: no response');
      return null;
    }

    // If already validated, use as is
    if (
      typeof response === 'object' &&
      'type' in response &&
      (response as A2UIResponse).type === 'a2ui'
    ) {
      const result = validateA2UIResponse(response);
      logger.a2uiValidated(!!result, result ? undefined : 'Pre-validated response invalid');

      if (result) {
        logger.info('A2UI rendering', {
          componentCount: result.components.length,
          componentTypes: result.components.map(c => c.type),
        });
        logger.a2uiPayload('validated-response', result);
      }
      return result;
    }

    // Try to parse if it's a string
    if (typeof response === 'string') {
      try {
        const parsed = JSON.parse(response);
        const result = validateA2UIResponse(parsed);
        logger.a2uiValidated(!!result, result ? undefined : 'Parsed string response invalid');
        return result;
      } catch {
        logger.a2uiValidated(false, 'JSON parse failed');
        return null;
      }
    }

    const result = validateA2UIResponse(response);
    logger.a2uiValidated(!!result, result ? undefined : 'Unknown response format invalid');
    return result;
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

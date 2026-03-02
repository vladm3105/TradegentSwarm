'use client';

import { useState, useEffect, useCallback } from 'react';
import { isClient, safeJsonParse } from '@/lib/utils';

export function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  // Get from local storage or use initial value
  const readValue = useCallback((): T => {
    if (!isClient()) {
      return initialValue;
    }

    const item = localStorage.getItem(key);
    return item ? safeJsonParse(item, initialValue) : initialValue;
  }, [initialValue, key]);

  const [storedValue, setStoredValue] = useState<T>(readValue);

  // Return a wrapped version of useState's setter function that persists to localStorage
  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      if (!isClient()) {
        console.warn(`Tried to set localStorage key "${key}" on server`);
        return;
      }

      const newValue = value instanceof Function ? value(storedValue) : value;
      localStorage.setItem(key, JSON.stringify(newValue));
      setStoredValue(newValue);

      // Dispatch storage event for other tabs
      window.dispatchEvent(
        new StorageEvent('storage', {
          key,
          newValue: JSON.stringify(newValue),
        })
      );
    },
    [key, storedValue]
  );

  // Read value on mount
  useEffect(() => {
    setStoredValue(readValue());
  }, [readValue]);

  // Listen for changes in other tabs
  useEffect(() => {
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === key && event.newValue) {
        setStoredValue(safeJsonParse(event.newValue, initialValue));
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [key, initialValue]);

  return [storedValue, setValue];
}

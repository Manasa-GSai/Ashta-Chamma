import * as matchers from '@testing-library/jest-dom/matchers';
import { expect } from 'vitest';

// Extend vitest's expect with @testing-library/jest-dom DOM matchers
expect.extend(matchers as Parameters<typeof expect.extend>[0]);

// ESM shim for react-is compatibility with Vite / Rolldown
export function isFragment(object: unknown): boolean {
  if (object == null || typeof object !== 'object') {
    return false;
  }
  const anyObj = object as { type?: unknown; $$typeof?: unknown };
  return (
    anyObj.type === Symbol.for('react.fragment') ||
    anyObj.$$typeof === Symbol.for('react.fragment')
  );
}

export default {
  isFragment,
};


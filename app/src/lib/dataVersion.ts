declare const __ATLAS_BUILD__: string;

// Every deployed client requests its own data version, so the previous release's
// one-hour browser cache cannot hide newly reviewed studies after a refresh.
export const dataUrl = (path: string) => `${path}?v=${encodeURIComponent(__ATLAS_BUILD__)}`;

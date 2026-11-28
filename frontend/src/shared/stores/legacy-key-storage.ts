import type { StateStorage } from "zustand/middleware";

/** `getItem` で新キーに値が無く旧キーに値があれば、その値を新キーへ移し替える `persist` の保存先 */
export const legacyKeyStorage = (
  storage: () => Storage,
  legacyName: string,
): StateStorage => ({
  getItem: (name) => {
    const current = storage().getItem(name);
    if (current !== null) return current;
    const legacy = storage().getItem(legacyName);
    if (legacy === null) return null;
    storage().setItem(name, legacy);
    storage().removeItem(legacyName);
    return legacy;
  },
  setItem: (name, value) => storage().setItem(name, value),
  removeItem: (name) => storage().removeItem(name),
});

export function referenceStorageKey(userId) {
  if (!userId) throw new Error("Sign in before managing reference contacts.");
  return `engen-reference-contacts:${userId}`;
}

export function readReferenceContacts(userId, storage = localStorage) {
  try {
    const saved = JSON.parse(storage.getItem(referenceStorageKey(userId)));
    return Array.isArray(saved) ? saved.filter((contact) => contact && typeof contact.id === "string" && typeof contact.name === "string") : [];
  } catch { return []; }
}

export function saveReferenceContacts(userId, contacts, storage = localStorage) {
  storage.setItem(referenceStorageKey(userId), JSON.stringify(contacts));
}

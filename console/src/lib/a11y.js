/* One polite live region for the whole app. Several competing regions means a screen reader
   never finishes a sentence, so everything announceable goes through here. */
let node = null;

export function registerLiveRegion(el) {
  node = el;
  return { destroy: () => (node = null) };
}

export function announce(message) {
  if (node) node.textContent = message;
}

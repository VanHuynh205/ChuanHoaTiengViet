import { useEffect, useState } from "react";
import { api } from "../lib/api";

export function useDictionaryRevision(token: string | null) {
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!token) return;
    let active = true;
    let running = false;
    const refresh = async () => {
      if (running) return;
      running = true;
      try {
        const result = await api.dictionaryRevision(token);
        if (active) setRevision(result.revision);
      } catch {
        // Normalize still revalidates through the server on every new input.
      } finally { running = false; }
    };
    void refresh();
    const timer = window.setInterval(refresh, 5000);
    window.addEventListener("focus", refresh);
    window.addEventListener("dictionary-updated", refresh);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("dictionary-updated", refresh);
    };
  }, [token]);
  return revision;
}

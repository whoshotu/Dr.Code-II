import { useEffect, useState } from "react";

// A tiny hook to persist state to localStorage across page reloads
export default function usePersistedState(key, initialValue) {
  const [state, setState] = useState(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw !== null ? JSON.parse(raw) : initialValue
    } catch {
      return initialValue
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(state))
    } catch {
      // ignore write errors
    }
  }, [key, state])

  return [state, setState]
}

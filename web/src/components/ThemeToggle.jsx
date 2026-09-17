import { useEffect, useState } from 'react'

export default function ThemeToggle() {
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  return (
    <button
      className="btn-ghost text-xs"
      onClick={() => setDark(!dark)}
      title={dark ? '切换到亮色' : '切换到暗色'}
    >
      {dark ? '🌙' : '☀️'}
    </button>
  )
}

'use client'

import { useState } from 'react'

export default function LanguageSwitcher() {
  const [lang, setLang] = useState<'en' | 'ar'>('en')

  return (
    <button
      onClick={() => setLang(lang === 'en' ? 'ar' : 'en')}
      className="px-3 py-1 text-sm border rounded hover:bg-gray-100"
    >
      {lang === 'en' ? 'العربية' : 'English'}
    </button>
  )
}

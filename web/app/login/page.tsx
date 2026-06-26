'use client'
import { useState } from 'react'
import { api } from '../lib/api'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const router = useRouter()

  const handleLogin = async () => {
    try {
      const data = await api.auth.login(email, password)
      localStorage.setItem('tms_token', data.access_token)
      router.push('/dashboard')
    } catch {
      setError('Invalid credentials')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded shadow w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-6 text-gray-800">Flow Ops TMS</h1>
        {error && <p className="text-red-500 mb-4 text-sm">{error}</p>}
        <input className="w-full border rounded px-3 py-2 mb-3 text-sm" placeholder="Email"
          value={email} onChange={e => setEmail(e.target.value)} />
        <input className="w-full border rounded px-3 py-2 mb-4 text-sm" placeholder="Password"
          type="password" value={password} onChange={e => setPassword(e.target.value)} />
        <button onClick={handleLogin}
          className="w-full bg-blue-600 text-white py-2 rounded text-sm font-medium hover:bg-blue-700">
          Sign In
        </button>
      </div>
    </div>
  )
}

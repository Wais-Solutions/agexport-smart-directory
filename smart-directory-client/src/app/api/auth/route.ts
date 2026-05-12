import { NextRequest, NextResponse } from 'next/server'

const API_URL        = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const SESSION_SECRET = process.env.SESSION_SECRET || ''

export async function POST(request: NextRequest) {
  const { username, password } = await request.json()

  // Delegar validación al backend
  const backendRes = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  if (!backendRes.ok) {
    return NextResponse.json({ error: 'Credenciales incorrectas' }, { status: 401 })
  }

  const { role, partner_id } = await backendRes.json()

  // Guardar rol y partner_id en la cookie (firmada con SESSION_SECRET como prefijo)
  const sessionValue = `${SESSION_SECRET}|${role}|${partner_id}`

  const response = NextResponse.json({ ok: true, role })
  response.cookies.set('admin_session', sessionValue, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 8,
    path: '/',
  })

  return response
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true })
  response.cookies.delete('admin_session')
  return response
}
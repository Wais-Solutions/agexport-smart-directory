import { NextRequest, NextResponse } from 'next/server'

const ADMIN_USER     = process.env.ADMIN_USERNAME  || 'admin'
const ADMIN_PASS     = process.env.ADMIN_PASSWORD  || ''
const SESSION_SECRET = process.env.SESSION_SECRET  || ''

export async function POST(request: NextRequest) {
  const { username, password } = await request.json()

  if (username !== ADMIN_USER || password !== ADMIN_PASS) {
    return NextResponse.json({ error: 'Credenciales incorrectas' }, { status: 401 })
  }

  const response = NextResponse.json({ ok: true })

  // Cookie de sesión: dura 8 horas, httpOnly para que JS no pueda leerla
  response.cookies.set('admin_session', SESSION_SECRET, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 8,  // 8 horas
    path: '/',
  })

  return response
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true })
  response.cookies.delete('admin_session')
  return response
}
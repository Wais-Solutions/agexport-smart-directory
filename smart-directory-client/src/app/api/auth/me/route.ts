import { NextRequest, NextResponse } from 'next/server'

const API_URL        = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const SESSION_SECRET = process.env.SESSION_SECRET || ''

export async function GET(request: NextRequest) {
  const session = request.cookies.get('admin_session')?.value
  if (!session) {
    return NextResponse.json({ error: 'No autenticado' }, { status: 401 })
  }

  const [secret, role, partner_id] = session.split('|')

  if (secret !== SESSION_SECRET) {
    return NextResponse.json({ error: 'Sesión inválida' }, { status: 401 })
  }

  if (role === 'partner') {
    const res = await fetch(`${API_URL}/specialties/${partner_id}`)
    const data = await res.json()
    return NextResponse.json({
        role,
        partner_id,
        partner_name: data.partner_name ?? null,
        username:     data.username ?? null,
    })
    }

  return NextResponse.json({ role, partner_id: null, partner_name: null, username: null })
}
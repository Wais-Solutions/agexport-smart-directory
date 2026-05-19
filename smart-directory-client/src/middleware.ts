import { NextRequest, NextResponse } from 'next/server'

// Rutas a las que un partner puede acceder
const PARTNER_ALLOWED = ['/especialidades']

// Rutas a las que solo admin puede acceder  
const ADMIN_ONLY = ['/']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  if (pathname === '/login' || pathname.startsWith('/api/auth')) {
    return NextResponse.next()
  }

  const session = request.cookies.get('admin_session')?.value
  if (!session) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  const [secret, role] = session.split('|')

  if (secret !== process.env.SESSION_SECRET) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  const isPartnerAllowed = PARTNER_ALLOWED.some(p => pathname.startsWith(p))
  const isAdminOnly      = ADMIN_ONLY.some(p => pathname === p)

  if (role === 'partner' && !isPartnerAllowed) {
    return NextResponse.redirect(new URL('/especialidades', request.url))
  }

  if (role === 'admin' && isPartnerAllowed) {
    return NextResponse.redirect(new URL('/', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)',
  ],
}
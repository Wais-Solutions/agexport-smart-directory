import { NextRequest, NextResponse } from 'next/server'

const PARTNER_PATHS = ['/especialidades']

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

  // Partner intentando acceder a rutas de admin → redirigir a /especialidades
  if (role === 'partner' && !PARTNER_PATHS.some(p => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL('/especialidades', request.url))
  }

  // Admin intentando acceder a /especialidades → redirigir a /
  if (role === 'admin' && PARTNER_PATHS.some(p => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL('/', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
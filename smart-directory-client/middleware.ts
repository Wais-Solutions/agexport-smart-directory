import { NextRequest, NextResponse } from 'next/server'

const ADMIN_ONLY_PATHS = ['/']   // rutas que solo admin puede ver
const PARTNER_PATHS    = ['/especialidades']  // rutas que partner puede ver

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Siempre permitir: login y api de auth
  if (pathname === '/login' || pathname.startsWith('/api/auth')) {
    return NextResponse.next()
  }

  const session = request.cookies.get('admin_session')?.value
  if (!session) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  // Formato de cookie: "SESSION_SECRET|role|partner_id"
  const [secret, role] = session.split('|')

  if (secret !== process.env.SESSION_SECRET) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  // Partner intentando acceder a rutas de admin
  if (role === 'partner' && !PARTNER_PATHS.some(p => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL('/especialidades', request.url))
  }

  // Admin tiene acceso a todo
  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
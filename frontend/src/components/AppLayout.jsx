import { Outlet, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Sidebar from '@/components/Sidebar'
import TopBar from '@/components/TopBar'
import { useSelector } from 'react-redux'
import { selectTenant } from '@/store'
import { cn } from '@/lib/utils'

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { currentTenant } = useSelector(selectTenant)
  const location = useLocation()

  // Close mobile drawer on navigation
  useEffect(() => { setMobileOpen(false) }, [location.pathname])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background md:p-3 md:gap-3">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar — hidden on mobile, slides in as drawer */}
      <div className={cn(
        'fixed inset-y-0 left-0 z-50 md:relative md:z-auto md:inset-auto',
        'transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]',
        mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
      )}>
        <Sidebar collapsed={collapsed} />
      </div>

      {/* Right column */}
      <div className="flex flex-1 flex-col overflow-visible gap-3 min-w-0">
        {/* Floating header */}
        <TopBar
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
          onMobileToggle={() => setMobileOpen((o) => !o)}
        />

        {/* Content */}
        <main className="flex-1 overflow-y-auto md:rounded-2xl">
          <div key={location.pathname + (currentTenant?.tenant_uuid ?? '')} className="animate-page-in p-3 sm:p-5">
            <Outlet key={currentTenant?.tenant_uuid ?? 'no-tenant'} />
          </div>
        </main>
      </div>
    </div>
  )
}

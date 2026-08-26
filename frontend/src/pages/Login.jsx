import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { loginThunk } from '@/store/slices/authSlice'
import { setTheme } from '@/store/slices/themeSlice'
import { selectTheme } from '@/store'
import { auth as authApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PhoneForwarded, Loader2, Shield, Eye, EyeOff, ArrowRight, Sun, Moon } from 'lucide-react'

// Assets
import logoLight from '@/assests/IHS Logo transparent.png'
import logoDark from '@/assests/IHS Logo for Black background.png'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/* ─────────────────────────────────────────────────────────────
   Enhanced Full-screen VoIP network background
   ───────────────────────────────────────────────────────────── */
function VoipBackground({ light = false }) {
  // Brand Palette Integration: Navy (#00416b) and Teal (#007d8f)
  const brandNavy = '#00416b'
  const brandTeal = '#007d8f'
  const brandTealLight = '#00a8c2'
  const brandNavyDark = '#00253d'

  const c = light ? {
    bg1: '#f8fafc', bg2: '#f1f5f9', bg3: '#e2e8f0',
    node: '#ffffff', nodeStroke: brandTeal, nodeStroke2: brandNavy,
    rack: '#e2e8f0', text: brandNavy, text2: brandTeal, text3: brandNavy,
    wave: brandTealLight, wire: '#cbd5e1', wireActive: brandTeal,
    pkt: brandTeal, led1: '#10b981', led2: brandTeal, led3: '#f59e0b',
    hs: brandNavy, vmBar: (i) => `hsl(188, ${60 + i * 5}%, ${40 + i * 3}%)`,
    msgIn: '#e0f2fe', msgInTxt: brandNavy,
    msgOut: '#ecfdf5', msgOutTxt: '#065f46',
    tdot: brandTeal, faxPaper: '#ffffff', faxLine: '#94a3b8',
    faxDisplay: '#f1f5f9', faxDisplayTxt: brandNavy,
    faxKey: '#f8fafc', wpScreen: '#f8fafc', wpKey: '#ffffff',
    wpCall: '#10b981', wpCallTxt: '#ffffff',
    dot: brandNavy, orb1: brandTeal, orb2: brandNavy,
    scan: brandTealLight, vigOuter: '#cbd5e1',
    badgeBg1: '#ecfdf5', badgeBdr1: '#10b981', badgeTxt1: '#065f46',
    badgeBg2: '#f0f9ff', badgeBdr2: brandTeal, badgeTxt2: brandNavy,
    shadowOpacity: '0.1'
  } : {
    bg1: '#020817', bg2: brandNavyDark, bg3: '#001220',
    node: brandNavy, nodeStroke: brandTealLight, nodeStroke2: brandTeal,
    rack: brandNavyDark, text: '#e2e8f0', text2: brandTealLight, text3: '#94a3b8',
    wave: brandTealLight, wire: '#1e293b', wireActive: brandTeal,
    pkt: '#22d3ee', led1: '#34d399', led2: brandTealLight, led3: '#fbbf24',
    hs: brandTealLight, vmBar: (i) => `hsl(188, ${80 + i * 2}%, ${50 + i * 2}%)`,
    msgIn: '#0c4a6e', msgInTxt: '#e0f2fe',
    msgOut: '#064e3b', msgOutTxt: '#d1fae5',
    tdot: brandTealLight, faxPaper: '#f8fafc', faxLine: '#64748b',
    faxDisplay: '#0f172a', faxDisplayTxt: '#38bdf8',
    faxKey: brandNavyDark, wpScreen: '#0f172a', wpKey: brandNavyDark,
    wpCall: '#059669', wpCallTxt: '#ffffff',
    dot: brandTealLight, orb1: brandTeal, orb2: brandNavy,
    scan: '#22d3ee', vigOuter: '#000000',
    badgeBg1: '#022c22', badgeBdr1: '#059669', badgeTxt1: '#34d399',
    badgeBg2: '#082f49', badgeBdr2: brandTeal, badgeTxt2: '#38bdf8',
    shadowOpacity: '0.4'
  }

  return (
    <svg
      key={light ? 'light' : 'dark'}
      viewBox="0 0 1000 700"
      /* Changed to xMaxYMid to pin the interesting parts of the SVG to the right side of the screen */
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 w-full h-full"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <style>{`
        /* ── Keyframes ── */
        @keyframes bg-wave {
          0%   { opacity: 0.6; transform: scale(0.4); stroke-width: 3px; }
          100% { opacity: 0; transform: scale(1.8); stroke-width: 0.5px; }
        }
        @keyframes bg-packet {
          0%        { offset-distance: 0%; opacity: 0; transform: scale(0.5); }
          10%, 90%  { opacity: 1; transform: scale(1.2); }
          100%      { offset-distance: 100%; opacity: 0; transform: scale(0.5); }
        }
        @keyframes bg-wire-flow {
          0%   { stroke-dashoffset: 20; }
          100% { stroke-dashoffset: 0; }
        }
        @keyframes bg-led {
          0%, 100% { opacity: 1; filter: drop-shadow(0 0 4px ${c.led2}); }
          50%      { opacity: 0.2; filter: none; }
        }
        @keyframes bg-fax {
          0%, 15%   { transform: translateY(0); }
          65%, 100% { transform: translateY(24px); }
        }
        @keyframes bg-vm {
          0%, 100% { transform: scaleY(0.15); }
          50%      { transform: scaleY(0.9); }
        }
        @keyframes bg-msg {
          0%   { opacity: 0; transform: translateY(10px) scale(0.95); }
          100% { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes bg-tdot {
          0%, 80%, 100% { opacity: 0.3; transform: translateY(0); }
          40%           { opacity: 1; transform: translateY(-4px); }
        }
        @keyframes bg-phone-ring {
          0%, 38%, 100% { transform: rotate(0deg); }
          40% { transform: rotate(-8deg); }
          42% { transform: rotate(8deg); }
          44% { transform: rotate(-4deg); }
          46% { transform: rotate(4deg); }
          48% { transform: rotate(0deg); }
        }
        @keyframes bg-float {
          0%, 100% { transform: translateY(0px); }
          50%      { transform: translateY(-10px); }
        }
        @keyframes bg-orb {
          0%, 100% { transform: scale(1) translate(0, 0); }
          50%      { transform: scale(1.1) translate(-20px, 15px); }
        }
        @keyframes bg-scan {
          0%   { transform: translateY(-100%); opacity: 0; }
          10%  { opacity: 0.6; }
          90%  { opacity: 0.6; }
          100% { transform: translateY(100%); opacity: 0; }
        }

        /* ── Bindings ── */
        .bw1 { animation: bg-wave 4s cubic-bezier(0.1, 0.5, 0.9, 0.1) infinite 0s; transform-origin: 240px 340px; }
        .bw2 { animation: bg-wave 4s cubic-bezier(0.1, 0.5, 0.9, 0.1) infinite 1.3s; transform-origin: 240px 340px; }
        .bw3 { animation: bg-wave 4s cubic-bezier(0.1, 0.5, 0.9, 0.1) infinite 2.6s; transform-origin: 240px 340px; }
        
        .bwire { animation: bg-wire-flow 1s linear infinite; }
        
        .bph { animation: bg-phone-ring 6s ease-in-out infinite; transform-origin: 240px 340px; }
        
        .bpk { animation: bg-packet 4.5s cubic-bezier(0.4, 0, 0.2, 1) infinite; }
        .bpk-d1 { animation-delay: 1.2s; }
        .bpk-d2 { animation-delay: 2.4s; }
        .bpk-d3 { animation-delay: 0.8s; }
        .bpk-d4 { animation-delay: 3.1s; }
        
        .bled1 { animation: bg-led 1.8s ease-in-out infinite 0s; }
        .bled2 { animation: bg-led 2.4s ease-in-out infinite 0.5s; }
        .bled3 { animation: bg-led 3.0s ease-in-out infinite 1.2s; }
        
        .bfax { animation: bg-fax 6s cubic-bezier(0.6, -0.28, 0.735, 0.045) infinite; }
        
        .bvm1 { animation: bg-vm 2s ease-in-out infinite 0s; transform-origin: bottom; }
        .bvm2 { animation: bg-vm 2s ease-in-out infinite 0.2s; transform-origin: bottom; }
        .bvm3 { animation: bg-vm 2s ease-in-out infinite 0.4s; transform-origin: bottom; }
        .bvm4 { animation: bg-vm 2s ease-in-out infinite 0.6s; transform-origin: bottom; }
        .bvm5 { animation: bg-vm 2s ease-in-out infinite 0.8s; transform-origin: bottom; }
        .bvm6 { animation: bg-vm 2s ease-in-out infinite 1.0s; transform-origin: bottom; }
        
        .bmsg1 { animation: bg-msg 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) both 1s; }
        .bmsg2 { animation: bg-msg 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) both 2.5s; }
        .bmsg3 { animation: bg-msg 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) both 4s; }
        
        .btd1 { animation: bg-tdot 1.4s ease-in-out infinite 0s; }
        .btd2 { animation: bg-tdot 1.4s ease-in-out infinite 0.2s; }
        .btd3 { animation: bg-tdot 1.4s ease-in-out infinite 0.4s; }
        
        .bfloat1 { animation: bg-float 8s ease-in-out infinite; }
        .bfloat2 { animation: bg-float 10s ease-in-out infinite 2s; }
        
        .borb1 { animation: bg-orb 25s ease-in-out infinite alternate; }
        .borb2 { animation: bg-orb 30s ease-in-out infinite alternate-reverse 5s; }
        
        .bscan { animation: bg-scan 4s linear infinite; }
      `}</style>

      <defs>
        <linearGradient id="bgGrad" x1="0" y1="0" x2="1000" y2="700" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={c.bg1} />
          <stop offset="50%" stopColor={c.bg2} />
          <stop offset="100%" stopColor={c.bg3} />
        </linearGradient>
        
        {/* Glow Effects */}
        <filter id="glowPkt" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
        <filter id="nodeShadow" x="-10%" y="-10%" width="130%" height="130%">
          <feDropShadow dx="0" dy="8" stdDeviation="12" floodColor="#000000" floodOpacity={c.shadowOpacity} />
        </filter>

        {/* Clip Paths */}
        <clipPath id="vm-clip"><rect x="60" y="455" width="180" height="120" rx="16" /></clipPath>
        <clipPath id="msg-clip"><rect x="750" y="430" width="190" height="150" rx="16" /></clipPath>
        <clipPath id="wp-clip"><rect x="52" y="80" width="176" height="140" rx="14" /></clipPath>
        <clipPath id="srv-clip"><rect x="530" y="240" width="120" height="140" rx="16"/></clipPath>

        <radialGradient id="vignette" cx="50%" cy="50%" r="50%">
          <stop offset="40%" stopColor="transparent" />
          <stop offset="100%" stopColor={c.vigOuter} stopOpacity={light ? '0.1' : '0.6'} />
        </radialGradient>
      </defs>

      {/* ── Background & Orbs ── */}
      <rect width="1000" height="700" fill="url(#bgGrad)" />
      <circle className="borb1" cx="200" cy="200" r="350" fill={c.orb1} opacity={light ? '0.04' : '0.05'} filter="blur(60px)" />
      <circle className="borb2" cx="850" cy="500" r="350" fill={c.orb2} opacity={light ? '0.04' : '0.1'} filter="blur(80px)" />

      {/* ── Network Wires (Paths) ── */}
      <g stroke={c.wire} strokeWidth="2" fill="none" className="bwire" strokeDasharray="8 6">
        <path id="pathPhoneToSrv" d="M290 340 C380 340 450 310 530 310" />
        <path id="pathWpToSrv" d="M228 150 C380 150 450 250 530 280" />
        <path id="pathVmToSrv" d="M240 515 C380 515 450 360 530 340" />
        <path id="pathSrvToHs" d="M650 310 C740 310 780 225 820 225" />
        <path id="pathSrvToFax" d="M590 380 C590 420 570 450 555 450" />
        <path id="pathSrvToMsg" d="M650 350 C700 350 730 460 750 490" />
      </g>

      {/* ── Data Packets (Animating along paths) ── */}
      <g fill={c.pkt} filter="url(#glowPkt)">
        <circle r="5" className="bpk" style={{ offsetPath: 'url(#pathPhoneToSrv)' }} />
        <circle r="5" className="bpk bpk-d1" style={{ offsetPath: 'url(#pathWpToSrv)' }} />
        <circle r="5" className="bpk bpk-d2" style={{ offsetPath: 'url(#pathVmToSrv)' }} />
        <circle r="5" className="bpk bpk-d3" style={{ offsetPath: 'url(#pathSrvToHs)' }} />
        <circle r="5" className="bpk bpk-d4" style={{ offsetPath: 'url(#pathSrvToFax)' }} />
        <circle r="5" className="bpk bpk-d1" style={{ offsetPath: 'url(#pathSrvToMsg)' }} />
      </g>

      {/* ── NODE 1: DESK PHONE ── */}
      <circle className="bw1" cx="240" cy="340" r="70" stroke={c.wave} fill="none" />
      <circle className="bw2" cx="240" cy="340" r="70" stroke={c.wave} fill="none" />
      <circle className="bw3" cx="240" cy="340" r="70" stroke={c.wave} fill="none" />
      <g className="bph" filter="url(#nodeShadow)">
        <rect x="180" y="290" width="110" height="100" rx="16" fill={c.node} stroke={c.nodeStroke} strokeWidth="2" />
        {/* Handset */}
        <path d="M170 300 Q160 340 170 380" stroke={c.nodeStroke2} strokeWidth="18" strokeLinecap="round" />
        <rect x="195" y="305" width="45" height="20" rx="4" fill={c.rack} />
        {/* Numpad */}
        {[0, 1, 2].map(col => [0, 1, 2, 3].map(row => (
          <circle key={`pk${col}${row}`} cx={205 + col * 15} cy={340 + row * 12} r="3" fill={c.text3} opacity="0.6" />
        )))}
        <circle cx="265" cy="315" r="8" fill={c.nodeStroke2} opacity="0.8" />
      </g>
      <text x="235" y="420" textAnchor="middle" fontSize="12" fill={c.text} fontWeight="bold" letterSpacing="1">DESK PHONE</text>

      {/* ── NODE 2: PBX SERVER CORE ── */}
      <g filter="url(#nodeShadow)">
        <rect x="530" y="240" width="120" height="140" rx="16" fill={c.node} stroke={c.nodeStroke} strokeWidth="2.5" />
        {/* Server Blades */}
        {[0, 1, 2, 3, 4].map(i => (
          <g key={`sr${i}`}>
            <rect x="546" y={255 + i * 22} width="88" height="16" rx="4" fill={c.rack} />
            <circle cx="560" cy={263 + i * 22} r="3" fill={c.led1} className={i % 2 === 0 ? "bled1" : "bled2"} filter="url(#glowPkt)" />
            <circle cx="572" cy={263 + i * 22} r="3" fill={c.led3} className={i % 3 === 0 ? "bled3" : "bled1"} filter="url(#glowPkt)" />
            <rect x="590" y={261 + i * 22} width="35" height="4" rx="2" fill={c.bg1} opacity="0.5" />
          </g>
        ))}
        {/* Scanner line overlay */}
        <rect x="530" y="240" width="120" height="10" fill={c.scan} opacity="0.2" className="bscan" clipPath="url(#srv-clip)" filter="url(#glowPkt)" />
      </g>
      <text x="590" y="405" textAnchor="middle" fontSize="13" fill={c.text} fontWeight="900" letterSpacing="2">PBX ENGINE</text>

      {/* ── NODE 3: HEADSET ── */}
      <g className="bfloat1" filter="url(#nodeShadow)">
        <path d="M830 200 A 35 35 0 0 1 890 200" stroke={c.nodeStroke} strokeWidth="6" strokeLinecap="round" fill="none" />
        <rect x="820" y="195" width="18" height="30" rx="8" fill={c.nodeStroke2} />
        <rect x="882" y="195" width="18" height="30" rx="8" fill={c.nodeStroke2} />
        <path d="M835 225 Q825 250 840 255" stroke={c.nodeStroke} strokeWidth="4" strokeLinecap="round" fill="none" />
        <circle cx="842" cy="256" r="5" fill={c.led1} filter="url(#glowPkt)" />
        <text x="860" y="285" textAnchor="middle" fontSize="12" fill={c.text} fontWeight="bold" letterSpacing="1">AGENT</text>
      </g>

      {/* ── NODE 4: WEB PHONE ── */}
      <g className="bfloat2" filter="url(#nodeShadow)">
        <rect x="52" y="80" width="176" height="140" rx="14" fill={c.node} stroke={c.nodeStroke2} strokeWidth="2" />
        <rect x="52" y="80" width="176" height="24" rx="14" fill={c.rack} />
        <rect x="52" y="94" width="176" height="10" fill={c.rack} />
        {/* Browser Dots */}
        <circle cx="68" cy="92" r="4" fill="#ef4444" />
        <circle cx="84" cy="92" r="4" fill="#f59e0b" />
        <circle cx="100" cy="92" r="4" fill="#10b981" />
        <rect x="115" y="86" width="100" height="12" rx="4" fill={c.bg1} />
        
        <g clipPath="url(#wp-clip)">
          <rect x="64" y="112" width="152" height="24" rx="6" fill={c.bg1} />
          <text x="140" y="129" textAnchor="middle" fontSize="13" fill={c.text} fontWeight="bold">Dialing...</text>
          {[0, 1].map(col => [0, 1, 2].map(row => (
            <rect key={`wk${col}${row}`} x={64 + row * 38} y={145 + col * 20} width="30" height="14" rx="4" fill={c.wire} opacity="0.4" />
          )))}
          <rect x="180" y="145" width="36" height="34" rx="8" fill={c.wpCall} />
        </g>
      </g>
      <text x="140" y="245" textAnchor="middle" fontSize="12" fill={c.text} fontWeight="bold" letterSpacing="1">WEB CLIENT</text>

      {/* ── NODE 5: VOICEMAIL ── */}
      <g filter="url(#nodeShadow)">
        <rect x="60" y="455" width="180" height="120" rx="16" fill={c.node} stroke={c.nodeStroke2} strokeWidth="2" />
        <g clipPath="url(#vm-clip)">
          {[0, 1, 2, 3, 4, 5, 6, 7, 8].map(i => (
            <rect key={`vm${i}`} className={`bvm${(i % 6) + 1}`} x={80 + i * 16} y={490} width="8" height="60" rx="4" fill={c.vmBar(i)} />
          ))}
        </g>
      </g>
      <text x="150" y="600" textAnchor="middle" fontSize="12" fill={c.text} fontWeight="bold" letterSpacing="1">VOICEMAIL</text>

      {/* ── NODE 6: FAX MACHINE ── */}
      <g filter="url(#nodeShadow)">
        <g className="bfax">
          <rect x="475" y="410" width="80" height="60" rx="2" fill={c.faxPaper} />
          {[0, 1, 2, 3].map(i => (
            <line key={`fl${i}`} x1="485" y1={420 + i * 10} x2={545 - i * 4} y2={420 + i * 10} stroke={c.faxLine} strokeWidth="2" strokeLinecap="round" />
          ))}
        </g>
        <rect x="460" y="450" width="190" height="120" rx="16" fill={c.node} stroke={c.nodeStroke2} strokeWidth="2" />
        <rect x="480" y="465" width="150" height="30" rx="6" fill={c.faxDisplay} />
        <text x="555" y="485" textAnchor="middle" fontSize="13" fill={c.faxDisplayTxt} fontFamily="monospace" fontWeight="bold">TX: 99%</text>
        <rect x="480" y="510" width="100" height="40" rx="6" fill={c.rack} />
        <circle cx="610" cy="530" r="12" fill={c.nodeStroke} />
      </g>
      <text x="555" y="595" textAnchor="middle" fontSize="12" fill={c.text} fontWeight="bold" letterSpacing="1">E-FAX</text>

      {/* ── NODE 7: MESSAGING ── */}
      <g filter="url(#nodeShadow)">
        <rect x="750" y="430" width="190" height="150" rx="16" fill={c.node} stroke={c.nodeStroke} strokeWidth="2" />
        <g clipPath="url(#msg-clip)">
          <g className="bmsg1">
            <rect x="765" y="460" width="110" height="30" rx="12" fill={c.msgIn} />
            <text x="820" y="479" textAnchor="middle" fontSize="12" fill={c.msgInTxt} fontWeight="500">System check?</text>
          </g>
          <g className="bmsg2">
            <rect x="825" y="500" width="100" height="30" rx="12" fill={c.msgOut} />
            <text x="875" y="519" textAnchor="middle" fontSize="12" fill={c.msgOutTxt} fontWeight="500">All green.</text>
          </g>
          <g className="bmsg3">
            <rect x="765" y="540" width="60" height="26" rx="13" fill={c.msgIn} />
            <circle className="btd1" cx="782" cy="553" r="3" fill={c.tdot} />
            <circle className="btd2" cx="795" cy="553" r="3" fill={c.tdot} />
            <circle className="btd3" cx="808" cy="553" r="3" fill={c.tdot} />
          </g>
        </g>
      </g>
      <text x="845" y="605" textAnchor="middle" fontSize="12" fill={c.text} fontWeight="bold" letterSpacing="1">SMS / CHAT</text>

      {/* ── Status Badges ── */}
      <g className="bfloat1">
        <rect x="680" y="375" width="130" height="36" rx="18" fill={c.badgeBg1} stroke={c.badgeBdr1} strokeWidth="1.5" />
        <circle cx="705" cy="393" r="6" fill={c.led1} className="bled1" filter="url(#glowPkt)" />
        <text x="750" y="398" fontSize="13" fill={c.badgeTxt1} fontWeight="bold" letterSpacing="1">ONLINE</text>
      </g>
      <g className="bfloat2">
        <rect x="310" y="150" width="140" height="36" rx="18" fill={c.badgeBg2} stroke={c.badgeBdr2} strokeWidth="1.5" />
        <text x="380" y="173" textAnchor="middle" fontSize="13" fill={c.badgeTxt2} fontWeight="bold" letterSpacing="1">SIP TRUNK</text>
      </g>

      {/* Vignette */}
      <rect width="1000" height="700" fill="url(#vignette)" pointerEvents="none" />
    </svg>
  )
}

export default function Login() {
  const [form, setForm] = useState({ email: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showForgot, setShowForgot] = useState(false)
  const [forgotEmail, setForgotEmail] = useState('')
  const [forgotLoading, setForgotLoading] = useState(false)
  const [forgotMsg, setForgotMsg] = useState('')
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const theme = useSelector(selectTheme)
  const isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)

  useEffect(() => {
    const prefill = searchParams.get('email')
    if (prefill) { setForm((f) => ({ ...f, email: prefill })); setForgotEmail(prefill) }
  }, [searchParams])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.email)               { setError('Email is required.'); return }
    if (!EMAIL_RE.test(form.email)){ setError('Enter a valid email address.'); return }
    if (!form.password)            { setError('Password is required.'); return }
    setLoading(true); setError('')
    try {
      const result = await dispatch(loginThunk({ username: form.email, password: form.password })).unwrap()
      navigate(result.user?.must_change_password ? '/change-password' : '/', { replace: true })
    } catch (err) {
      setError(
        err?.detail ||
        err?.non_field_errors?.[0] ||
        'Invalid credentials. Please try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  const handleForgot = async (e) => {
    e.preventDefault()
    if (!forgotEmail || !EMAIL_RE.test(forgotEmail)) { setForgotMsg('Enter a valid email address.'); return }
    setForgotLoading(true); setForgotMsg('')
    try {
      const { data } = await authApi.forgotPassword(forgotEmail)
      setForgotMsg(data.detail || 'If an account with that email exists, a reset email has been sent.')
    } catch {
      setForgotMsg('If an account with that email exists, a reset email has been sent.')
    } finally {
      setForgotLoading(false)
    }
  }

  return (
    <div className="min-h-screen overflow-hidden flex bg-background">

      {/* ── Left panel — SVG background (visible on md+) ── */}
      <div className="hidden md:flex md:w-[55%] lg:w-[62%] xl:w-[68%] 2xl:w-3/4 relative overflow-hidden min-h-screen">
        <VoipBackground light={!isDark} />
      </div>

      {/* ── Right panel — login form ── */}
      <div className="relative flex flex-col items-center justify-center w-full md:w-[45%] lg:w-[38%] xl:w-[32%] 2xl:w-1/4 min-h-screen px-6 md:px-8 lg:px-10 py-10"
           style={{
             background: isDark ? 'rgba(2,8,23,0.95)' : 'rgba(255,255,255,0.97)',
             borderLeft: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.08)',
           }}>

        {/* ── Theme toggle — top-right of left panel ── */}
        <button
          onClick={() => dispatch(setTheme(isDark ? 'light' : 'dark'))}
          className="absolute top-4 right-4 z-20 flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium backdrop-blur-sm transition-all
            border border-black/10 bg-black/5 text-black/50 hover:bg-black/10 hover:text-black/80
            dark:border-white/10 dark:bg-white/5 dark:text-white/50 dark:hover:bg-white/10 dark:hover:text-white/90"
        >
          {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          {isDark ? 'Light' : 'Dark'}
        </button>

      {/* ── Login card ── */}
      <div className="w-full max-w-sm mx-auto animate-in fade-in slide-in-from-left-8 duration-500">
        <div>

          {/* Logo */}
          <div className="flex justify-center mb-8">
            <div className="flex flex-col items-center gap-2">
              <img 
                src={logoLight} 
                alt="Cloud PBX" 
                className="h-16 w-auto object-contain animate-logo-bounce" 
              />
              <div className="text-center">
                <p className="text-[10px] font-bold leading-tight text-muted-foreground uppercase tracking-[0.2em] opacity-80" 
                   style={{ color: isDark ? '#38bdf8' : '#007d8f' }}>
                  Unified Communication
                </p>
              </div>
            </div>
          </div>

          {!showForgot ? (
            <>
              <div className="mb-6 text-center">
                <h2 className="text-2xl font-extrabold tracking-tight text-foreground">Welcome back</h2>
                <p className="mt-1 text-sm text-muted-foreground">Sign in to your account to continue</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <div className="flex items-start gap-2.5 rounded-xl border border-destructive/25 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive">
                    <Shield className="h-4 w-4 mt-0.5 shrink-0" />
                    {error}
                  </div>
                )}

                <div className="space-y-1.5">
                  <Label htmlFor="email" className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Email</Label>
                  <Input
                    id="email" type="email" placeholder="you@example.com"
                    autoComplete="email" autoFocus
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    disabled={loading}
                    className="h-11 bg-background/50 backdrop-blur-sm border-muted-foreground/20 focus-visible:ring-[#007d8f]"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="password" className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Password</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      autoComplete="current-password"
                      value={form.password}
                      onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                      disabled={loading}
                      className="pr-10 h-11 bg-background/50 backdrop-blur-sm border-muted-foreground/20 focus-visible:ring-[#007d8f]"
                    />
                    <button type="button" tabIndex={-1}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                      onClick={() => setShowPassword(!showPassword)}>
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <Button type="submit" className="w-full h-12 text-sm font-bold mt-4 text-white transition-all hover:opacity-90 active:scale-[0.98]" disabled={loading}
                        style={{ 
                          background: 'linear-gradient(135deg, #00416b, #007d8f)', 
                          boxShadow: '0 4px 15px rgba(0, 125, 143, 0.3)' 
                        }}>
                  {loading
                    ? <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Authenticating…</>
                    : <><span>Sign in</span><ArrowRight className="h-4 w-4 ml-2" /></>}
                </Button>

                <div className="text-center pt-2">
                  <button type="button"
                    className="text-xs font-medium text-muted-foreground hover:text-[#007d8f] transition-colors underline-offset-4 hover:underline"
                    onClick={() => { setShowForgot(true); setForgotMsg(''); setError('') }}>
                    Forgot your password?
                  </button>
                </div>
              </form>
            </>
          ) : (
            <>
              <div className="mb-6 text-center">
                <h2 className="text-2xl font-extrabold tracking-tight text-foreground">Reset password</h2>
                <p className="mt-1 text-sm text-muted-foreground">We'll send a temporary password to your email.</p>
              </div>

              <form onSubmit={handleForgot} className="space-y-4">
                {forgotMsg && (
                  <div className="rounded-xl border border-primary/25 bg-primary/8 px-3.5 py-2.5 text-sm text-primary">
                    {forgotMsg}
                  </div>
                )}
                <div className="space-y-1.5">
                  <Label htmlFor="forgot-email" className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Email</Label>
                  <Input
                    id="forgot-email" type="email" placeholder="you@example.com"
                    autoFocus value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    disabled={forgotLoading}
                    className="h-11 bg-background/50 backdrop-blur-sm border-muted-foreground/20 focus-visible:ring-[#007d8f]"
                  />
                </div>
                <Button type="submit" className="w-full h-12 font-bold text-white transition-all hover:opacity-90 active:scale-[0.98] mt-2" disabled={forgotLoading || !forgotEmail}
                        style={{ background: 'linear-gradient(135deg, #00416b, #007d8f)', boxShadow: '0 4px 15px rgba(0, 125, 143, 0.3)' }}>
                  {forgotLoading ? <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Sending…</> : 'Send reset email'}
                </Button>
                <div className="text-center pt-2">
                  <button type="button"
                    className="text-xs font-medium text-muted-foreground hover:text-[#007d8f] transition-colors underline-offset-4 hover:underline"
                    onClick={() => { setShowForgot(false); setForgotMsg('') }}>
                    ← Back to sign in
                  </button>
                </div>
              </form>
            </>
          )}
        </div>
      </div>

      {/* Footer */}
      <p className="mt-6 text-center text-xs font-medium text-muted-foreground/80 dark:text-muted-foreground/50">
        © {new Date().getFullYear()} Cloud PBX. All rights reserved.
      </p>

    </div>{/* end right panel */}

    </div>
  )
}
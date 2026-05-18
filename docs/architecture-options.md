# FreeSWITCH + Django PBX Architecture Options

## Hardware Available
- **Houston**: VMware Host — Intel Xeon Platinum 8180, 32 vCPU, 128GB RAM, 1TB SAS SSD
- **Dallas**: VMware Host — Intel Xeon Platinum 8180, 32 vCPU, 128GB RAM, 1TB SAS SSD
- **Current Load**: 800+ simultaneous calls

---

## Option 1 — Manual Assignment (No Change)

### Description
Clients are manually assigned to Houston or Dallas. When a server is overloaded or fails, clients are manually moved to the other server by updating their SIP server configuration.

### Architecture
```
Client A, B, C → Houston Public IP (direct)
Client D, E, F → Dallas Public IP  (direct)

Manual move when needed
```

### Server Requirements

#### Houston
| VM | Role | vCPU | RAM | Storage |
|----|------|------|-----|---------|
| VM1 | FreeSWITCH | 8 | 16GB | 100GB |
| VM2 | Django + Nginx | 4 | 8GB | 50GB |
| VM3 | PostgreSQL Primary | 8 | 32GB | 500GB |
| **Total** | | **20 vCPU** | **56GB** | **650GB** |

#### Dallas
| VM | Role | vCPU | RAM | Storage |
|----|------|------|-----|---------|
| VM4 | FreeSWITCH | 8 | 16GB | 100GB |
| VM5 | Django + Nginx | 4 | 8GB | 50GB |
| VM6 | PostgreSQL Standby | 8 | 32GB | 500GB |
| **Total** | | **20 vCPU** | **56GB** | **650GB** |

**Total VMs: 6**

### Pros
- Simplest setup
- No extra tools needed
- You already do this today

### Cons
- Manual intervention required on failure
- Downtime depends on how fast you respond
- No automatic failover

### Cost
| Item | Cost |
|------|------|
| Hardware | $0 (existing) |
| Software | $0 |
| **Total** | **$0/month** |

### Failover
| Scenario | Downtime | Action |
|----------|----------|--------|
| Houston fails | Until manual intervention | Manually update client SIP config |
| Dallas fails | Until manual intervention | Manually update client SIP config |

---

## Option 2 — Two Subdomains + Cloudflare Failover (Recommended)

### Description
Clients are assigned to a subdomain (houston or dallas) instead of a direct IP. Cloudflare monitors both sites and automatically redirects traffic if a site goes down. You can also manually switch via Cloudflare dashboard.

### Architecture
```
Client A, B, C → houston.sip.yourcompany.com → Houston IP
                       (if Houston dies → auto switches to Dallas IP)

Client D, E, F → dallas.sip.yourcompany.com  → Dallas IP
                       (if Dallas dies → auto switches to Houston IP)

Cloudflare health checks TCP port 5060 every 30 seconds
```

### Server Requirements

#### Houston
| VM | Role | vCPU | RAM | Storage |
|----|------|------|-----|---------|
| VM1 | FreeSWITCH | 8 | 16GB | 100GB |
| VM2 | Django + Nginx | 4 | 8GB | 50GB |
| VM3 | PostgreSQL Primary + Patroni | 8 | 32GB | 500GB |
| **Total** | | **20 vCPU** | **56GB** | **650GB** |

#### Dallas
| VM | Role | vCPU | RAM | Storage |
|----|------|------|-----|---------|
| VM4 | FreeSWITCH | 8 | 16GB | 100GB |
| VM5 | Django + Nginx | 4 | 8GB | 50GB |
| VM6 | PostgreSQL Standby + Patroni | 8 | 32GB | 500GB |
| **Total** | | **20 vCPU** | **56GB** | **650GB** |

**Total VMs: 6**

### Cloudflare Configuration
```
houston.sip.yourcompany.com
  Primary:  Houston IP  (health check TCP 5060)
  Fallback: Dallas IP   (used only if Houston fails)

dallas.sip.yourcompany.com
  Primary:  Dallas IP   (health check TCP 5060)
  Fallback: Houston IP  (used only if Dallas fails)

Health check: TCP port 5060, every 30 seconds, DNS only (grey cloud)
```

### Pros
- Keeps your current manual assignment approach
- Automatic failover — no manual intervention needed
- Manual override via Cloudflare dashboard anytime
- Clients never need reconfiguration during failover
- Both sites active simultaneously
- Minimal infrastructure change

### Cons
- 30-60 second failover time (DNS TTL)
- Active calls drop on site failure (unavoidable in VoIP)
- Clients still manually assigned to a site initially

### Cost
| Item | Cost |
|------|------|
| Hardware | $0 (existing) |
| Cloudflare Load Balancer | $5/month |
| WireGuard VPN (Houston↔Dallas) | $0 |
| **Total** | **$5/month** |

### Failover Matrix
| Scenario | Downtime | Action |
|----------|----------|--------|
| Houston FS crashes | **30-60 sec** | Cloudflare DNS switches to Dallas |
| Dallas FS crashes | **30-60 sec** | Cloudflare DNS switches to Houston |
| Houston site down | **30-60 sec** | Cloudflare DNS switches to Dallas |
| Dallas site down | **30-60 sec** | Cloudflare DNS switches to Houston |
| Manual transfer | **30-60 sec** | Disable site in Cloudflare dashboard |
| Houston PG fails | **30 sec** | Patroni promotes Dallas PG |
| Dallas PG fails | **0 sec** | Houston continues normally |

### Database Replication
```
Houston PostgreSQL (Primary) → async replication → Dallas PostgreSQL (Standby)
Patroni monitors both nodes
On Houston failure: Patroni auto-promotes Dallas to Primary
On Houston recovery: Dallas demotes back to Standby
```

---

## Option 3 — Kamailio + Full Auto Load Balancing + Failover

### Description
Kamailio acts as a SIP proxy in front of both FreeSWITCH nodes. All clients point to a single SIP domain. Kamailio automatically distributes calls and handles failover transparently — clients never know which server handled their call.

### Architecture
```
All Clients → sip.yourcompany.com (Cloudflare DNS)
                        ↓
              Houston Kamailio ←sync→ Dallas Kamailio
              (active)                (active)
                  ↓                        ↓
           Houston FS                 Dallas FS
                  ↓                        ↓
           Houston Django            Dallas Django
                  ↓                        ↓
           PG Primary     ←async→    PG Standby
           (Houston)       repl      (Dallas)
```

### Server Requirements

#### Houston
| VM | Role | vCPU | RAM | Storage |
|----|------|------|-----|---------|
| VM1 | Kamailio + HAProxy | 2 | 4GB | 20GB |
| VM2 | FreeSWITCH | 8 | 16GB | 100GB |
| VM3 | Django + Nginx | 4 | 8GB | 50GB |
| VM4 | PostgreSQL Primary + Patroni | 8 | 32GB | 500GB |
| **Total** | | **22 vCPU** | **60GB** | **670GB** |

#### Dallas
| VM | Role | vCPU | RAM | Storage |
|----|------|------|-----|---------|
| VM5 | Kamailio + HAProxy | 2 | 4GB | 20GB |
| VM6 | FreeSWITCH | 8 | 16GB | 100GB |
| VM7 | Django + Nginx | 4 | 8GB | 50GB |
| VM8 | PostgreSQL Standby + Patroni | 8 | 32GB | 500GB |
| **Total** | | **22 vCPU** | **60GB** | **670GB** |

**Total VMs: 8**

### How Kamailio Works
- All phones register to `sip.yourcompany.com`
- Kamailio receives registration, stores in shared DB, forwards to FreeSWITCH
- Inbound call arrives → Kamailio routes to Houston FS or Dallas FS based on config
- Houston FS fails → Kamailio detects via OPTIONS ping in 10 seconds → routes all calls to Dallas FS
- No DNS change, no phone re-registration needed
- Cross-site calls: Houston phone calls Dallas phone → Kamailio routes transparently

### Kamailio Configuration
```
dispatcher.list:
  setid=1  Houston FS  weight=1  (active)
  setid=1  Dallas FS   weight=0  (standby only — no load balancing)

OPTIONS ping every 10 seconds
On failure: remove from active set, route to remaining node
On recovery: add back to active set
```

### Pros
- Single SIP domain for all clients
- Fastest failover — 10-30 seconds (no DNS TTL wait)
- Cross-site calls work transparently
- No client reconfiguration ever needed
- Most scalable — add FS nodes without touching clients

### Cons
- Most complex setup
- Kamailio requires expertise to configure and maintain
- Two extra VMs (VM1, VM5)
- Overkill if you don't need auto load balancing

### Cost
| Item | Cost |
|------|------|
| Hardware | $0 (existing) |
| Cloudflare Load Balancer | $5/month |
| WireGuard VPN (Houston↔Dallas) | $0 |
| Kamailio (open source) | $0 |
| **Total** | **$5/month** |

### Failover Matrix
| Scenario | Downtime | Action |
|----------|----------|--------|
| Houston FS crashes | **10-30 sec** | Kamailio OPTIONS detects, routes to Dallas FS |
| Dallas FS crashes | **10-30 sec** | Kamailio OPTIONS detects, routes to Houston FS |
| Houston Kamailio crashes | **30-60 sec** | Cloudflare DNS switches to Dallas Kamailio |
| Houston site down | **30-60 sec** | Cloudflare DNS + Patroni promote |
| Dallas site down | **0 sec** | Houston continues normally |
| Houston PG fails | **30 sec** | Patroni auto-promotes Dallas |
| Manual transfer | **Instant** | Update Kamailio dispatcher config |

---

## Comparison Summary

| Feature | Option 1 | Option 2 | Option 3 |
|---------|----------|----------|----------|
| Auto failover | No | Yes (30-60 sec) | Yes (10-30 sec) |
| Manual failover | Yes (slow) | Yes (Cloudflare dashboard) | Yes (Kamailio config) |
| Both sites active | Yes (manual split) | Yes (subdomain split) | Yes (auto) |
| Single SIP domain | No | No (subdomains) | Yes |
| Client reconfiguration on failover | Yes (manual) | No | No |
| Extra infrastructure | None | Cloudflare LB | Cloudflare LB + Kamailio |
| Complexity | Low | Medium | High |
| Total VMs | 6 | 6 | 8 |
| Monthly cost | $0 | $5 | $5 |
| Best for | Simple setups | Your use case | Large scale / call centers |

---

## Recommendation

**Option 2** is the best fit for your current needs:
- Keeps your existing manual client assignment workflow
- Adds automatic failover with no manual intervention
- Both Houston and Dallas active simultaneously
- Minimal infrastructure change — 6 VMs, same as today
- Only $5/month additional cost
- Can upgrade to Option 3 later if needed without rebuilding

---

## Network Requirements (Options 2 & 3)

| Connection | Protocol | Port | Notes |
|------------|----------|------|-------|
| Phones → FS | SIP UDP/TCP | 5060/5080 | Public |
| Phones → FS | RTP | 16384-32768 | Media, public |
| FS → Django | HTTP | 8000 | Internal only |
| Houston ↔ Dallas | PG replication | 5432 | WireGuard VPN |
| Houston ↔ Dallas | Patroni | 8008 | WireGuard VPN |
| Kamailio → FS (Option 3) | SIP | 5060/5080 | Internal only |

**Houston ↔ Dallas replication must run over WireGuard VPN — never expose PostgreSQL to public internet.**

---

## Migration Plan (Option 2 — Recommended)

### Phase 1 — Houston Setup (Week 1)
1. Create 3 VMs on Houston VMware host
2. Install FreeSWITCH + Django (current stack already developed)
3. Move one test client to Houston
4. Verify calls, CDR, features work

### Phase 2 — Dallas Setup (Week 2)
1. Create 3 VMs on Dallas VMware host
2. Install FreeSWITCH + Django
3. Set up PostgreSQL streaming replication Houston → Dallas
4. Install Patroni on both PG nodes
5. Test automatic PG failover

### Phase 3 — Cloudflare (Week 3)
1. Create `houston.sip.yourcompany.com` → Houston IP
2. Create `dallas.sip.yourcompany.com` → Dallas IP
3. Add fallback records on each
4. Enable health checks on TCP 5060
5. Move clients from direct IP to subdomains

### Phase 4 — Cutover (Week 4)
1. Move all clients to new subdomains
2. Verify failover works (test by stopping Houston FS)
3. Decommission old Asterisk servers
4. Monitor for 1 week

---

*Document generated: 2026-03-27*

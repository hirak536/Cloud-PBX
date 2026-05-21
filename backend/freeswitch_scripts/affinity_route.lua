-- affinity_route.lua
--
-- Runtime sticky-routing lookup. Called from the dialplan as:
--   <action application="lua" data="affinity_route.lua TENANT_UUID FALLBACK_TYPE FALLBACK_TARGET TENANT_CTX"/>
--
-- Looks up the calling number in v_caller_extension_affinity for the tenant;
-- if found, transfers to that extension. Otherwise transfers to the fallback.
--
-- Cached XML is identical for every caller (just the lua action) — the per-call
-- decision happens here, at execute time, using the live caller_id_number.

local tenant_uuid    = argv[1] or ""
local fallback_type  = argv[2] or "hangup"   -- "extension" | "transfer" | "hangup"
local fallback_data  = argv[3] or ""         -- target ext or transfer target
local tenant_ctx     = argv[4] or "public"   -- e.g. "default-IHDT"

local caller = session:getVariable("caller_id_number") or ""

-- Normalize: strip non-digits, drop leading "1", keep last 10 (US).
local digits = caller:gsub("%D", "")
if #digits > 10 and digits:sub(1,1) == "1" then
    digits = digits:sub(2)
end
if #digits >= 10 then
    digits = digits:sub(-10)
end

freeswitch.consoleLog("INFO", string.format(
    "[affinity_route] tenant=%s caller=%s normalized=%s\n",
    tenant_uuid, caller, digits))

local routed_ext = nil

if tenant_uuid ~= "" and #digits == 10 then
    -- Reuse the connection FreeSWITCH already opens; named handle 'core' uses
    -- the dsn from switch.conf.xml. If you prefer an explicit connection, use:
    --   local dbh = freeswitch.Dbh("pgsql://hostaddr=127.0.0.1 dbname=ihspbx user=ihspbx password=...")
    local dbh = freeswitch.Dbh("pgsql://hostaddr=127.0.0.1 dbname=ihspbx user=ihspbx password=__PG_PASSWORD__")
    if dbh:connected() then
        local sql = string.format(
            "SELECT extension_number FROM v_caller_extension_affinity " ..
            "WHERE tenant_uuid = '%s' AND caller_number = '%s' LIMIT 1",
            tenant_uuid, digits)
        dbh:query(sql, function(row)
            if row.extension_number and row.extension_number ~= "" then
                routed_ext = row.extension_number
            end
        end)
        dbh:release()
    else
        freeswitch.consoleLog("ERR", "[affinity_route] could not connect to pgsql\n")
    end
end

if routed_ext then
    -- Strip optional tenant suffix: "901-IHDT" → "901"
    local ext_plain = routed_ext:match("^(%d+)") or routed_ext
    freeswitch.consoleLog("INFO", string.format(
        "[affinity_route] HIT  caller=%s -> ext=%s ctx=%s\n",
        digits, ext_plain, tenant_ctx))
    session:execute("transfer", ext_plain .. " XML " .. tenant_ctx)
    return
end

-- No affinity match → fallback
freeswitch.consoleLog("INFO", string.format(
    "[affinity_route] MISS caller=%s, fallback_type=%s data=%s\n",
    digits, fallback_type, fallback_data))

if fallback_type == "extension" then
    local ext_plain = fallback_data:match("^(%d+)") or fallback_data
    session:execute("transfer", ext_plain .. " XML " .. tenant_ctx)
elseif fallback_type == "transfer" then
    session:execute("transfer", fallback_data)
else
    session:hangup("NORMAL_CLEARING")
end

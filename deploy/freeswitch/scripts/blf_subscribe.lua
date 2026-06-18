-- blf_subscribe.lua  (IHS-PBX, self-contained — no FusionPBX framework)
--
-- Drives BLF lamps for "flow+" feature-code toggles (Call Flows), the same way
-- FusionPBX's blf_subscribe.lua does, but state is read from FreeSWITCH mod_db
-- instead of SQL so it has zero external dependencies.
--
-- Phone programs a BLF key with value:  flow+*<featurecode>   e.g. flow+*800
-- When the phone SUBSCRIBEs, FreeSWITCH fires PRESENCE_PROBE(proto=flow); we
-- look up the current state and publish a PRESENCE_IN so the lamp lights.
--
-- State source (written by the dialplan toggle-exec):
--   mod_db key:  call_flow_status/<*featurecode>@<domain>   value 'true'|'false'
-- Polarity (matches FusionPBX): status 'false' => lamp LIT (red), 'true' => off.
--
-- Install: enable as a startup-script in lua.conf.xml:
--   <param name="startup-script" value="blf_subscribe.lua flow"/>
-- then reloadxml + reload mod_lua (or restart freeswitch).

local api = freeswitch.API()

local function split_first(s, sep)
	local i = s:find(sep, 1, true)
	if not i then return s end
	return s:sub(1, i - 1), s:sub(i + #sep)
end

-- Publish the lamp. `on`=true => confirmed (lit/red), false => terminated (off).
-- `to` is the full subscribed id, e.g. "flow+*800@domain".
local function turn_lamp(on, to)
	local userid, domain = split_first(to, "@")
	local proto, after = split_first(userid, "+")
	local user
	if after ~= userid then
		user = after .. "@" .. domain    -- "*800@domain"
	else
		proto, user = "sip", to
	end

	local uuid = trim(api:executeString("create_uuid"))
	local e = freeswitch.Event("PRESENCE_IN")
	e:addHeader("proto", proto)                       -- "flow"
	e:addHeader("event_type", "presence")
	e:addHeader("alt_event_type", "dialog")
	e:addHeader("Presence-Call-Direction", "outbound")
	e:addHeader("from", user)
	e:addHeader("login", user)
	e:addHeader("unique-id", uuid)
	e:addHeader("status", "Active (1 waiting)")
	if on then
		e:addHeader("answer-state", "confirmed")
		e:addHeader("rpid", "unknown")
		e:addHeader("event_count", "1")
	else
		e:addHeader("answer-state", "terminated")
	end
	e:fire()
end

function trim(s) return (s:gsub("^%s*(.-)%s*$", "%1")) end

-- Resolve current call-flow status from mod_db for a "flow+*fc@domain" id.
local function flow_status(to)
	local userid, domain = split_first(to, "@")
	local _, fc = split_first(userid, "+")        -- "*800"
	if not domain or fc == userid then return nil end
	local key = "call_flow_status/" .. fc .. "@" .. domain
	local val = trim(api:executeString("db select/" .. key))
	if val == "" then return nil end              -- unknown => leave lamp alone
	return val
end

local con = freeswitch.EventConsumer("PRESENCE_PROBE")
freeswitch.consoleLog("notice", "[blf_subscribe] flow BLF handler started\n")

while true do
	local event = con:pop(1)
	if event then
		local proto = event:getHeader("proto")
		if proto == "flow" then
			local to = event:getHeader("to") or event:getHeader("from")
			local expires = tonumber(event:getHeader("expires") or "0")
			if to and expires and expires > 0 then
				local status = flow_status(to)
				if status ~= nil then
					-- FusionPBX polarity: lit when status == 'false'
					turn_lamp(status == "false", to)
					freeswitch.consoleLog("notice",
						"[blf_subscribe] flow " .. to .. " status=" .. status .. "\n")
				else
					freeswitch.consoleLog("warning",
						"[blf_subscribe] no state for " .. tostring(to) .. "\n")
				end
			end
		end
	end
end

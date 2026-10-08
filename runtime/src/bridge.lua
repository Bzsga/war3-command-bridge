-- Imported into the MPQ and loaded by KKWE's Lua module loader.
local native_jass=require 'jass.common'
local function mark(stage,text)
    native_jass.PreloadGenClear()
    native_jass.PreloadGenStart()
    native_jass.Preload(text)
    native_jass.PreloadGenEnd('Logs\\WB-'..__BUILD__..'-'..stage..'.pld')
end
mark('module-enter','Lua module entered; '..tostring(_VERSION)..'; io='..type(io)..'; open='..type(io and io.open))
local json = (function()
__JSON_CODEC__
end)()
local session = __SESSION__
local build = __BUILD__
local paths = __PATHS__
local base, encoding
local function read(path)
    local f=io.open(path,'rb');if not f then return nil end
    local s=f:read('*a');f:close();return s
end
local function write(path,s)
    local f,e=io.open(path,'wb');assert(f,e);assert(f:write(s));assert(f:close())
end
for _,p in ipairs(paths) do
    local ok,data=pcall(read,p.path..'/probe.txt')
    if ok and data==session then base=p.path;encoding=p.encoding;break end
end
mark('module-probe',base and ('file IO passed: '..encoding) or 'file IO probe failed')
assert(base,'file_io_probe_failed: no working path encoding')
write(base..'/bootstrap.json',json.encode({session=session,build=build,stage='file_io_ready',path_encoding=encoding}))
local jass=require 'jass.common'
local g=require 'jass.globals'
assert(g.WB_Protocol==1,'JASS globals unavailable')
local last_seq, ticks, cache = '',0,{}
local function snapshot()
    jass.ExecuteFunc('WB_Observe')
    local function unit(u)
        if u==nil or u==0 or jass.GetUnitTypeId(u)==0 then return {exists=false} end
        return {exists=true,type_id=jass.GetUnitTypeId(u),handle_id=jass.GetHandleId(u),life=jass.GetUnitState(u,jass.UNIT_STATE_LIFE),x=jass.GetUnitX(u),y=jass.GetUnitY(u),order=jass.GetUnitCurrentOrder(u),paused=jass.IsUnitPaused(u)}
    end
    return {actor=unit(g.WB_Actor),target=unit(g.WB_Target),gold=jass.GetPlayerState(jass.Player(0),jass.PLAYER_STATE_RESOURCE_GOLD),deaths=g.WB_Deaths,rewards=g.WB_Rewards,live_test_units=g.WB_LiveUnits,observed_map_units=g.WB_ObservedUnits,round=g.WB_Round,order_accepted=g.WB_OrderOK,ticks=ticks,game_seconds=g.WB_GameSeconds,active_death_triggers=g.WB_TriggersCreated-g.WB_TriggersDestroyed,triggers_created=g.WB_TriggersCreated,triggers_destroyed=g.WB_TriggersDestroyed}
end
local actions={prepare=1,order=2,reset=3}
local function execute(req)
    assert(type(req)=='table','request must be an object')
    assert(req.session==session,'wrong_session')
    assert(type(req.id)=='string' and #req.id>0 and #req.id<=80,'bad_request_id')
    assert(type(req.op)=='string','bad_operation')
    local fingerprint=json.encode(req)
    if cache[req.id] then
        assert(cache[req.id].fingerprint==fingerprint,'request_id_conflict')
        local r=cache[req.id].response
        return {ok=r.ok,id=r.id,session=session,build=build,result=r.result,replayed=true}
    end
    assert(req.op=='ping' or req.op=='snapshot' or actions[req.op],'unknown_operation')
    assert(req.args==nil or type(req.args)=='table','args must be an object')
    if req.op=='order' then
        assert(req.args and req.args.command=='attack','unsupported_order')
        assert(g.WB_Actor~=nil and g.WB_Actor~=0 and g.WB_Target~=nil and g.WB_Target~=0,'scenario_not_prepared')
    end
    if actions[req.op] then
        g.WB_Action=actions[req.op]
        jass.ExecuteFunc('WB_Dispatch')
    end
    local response={ok=true,id=req.id,session=session,build=build,result=snapshot(),replayed=false}
    cache[req.id]={fingerprint=fingerprint,response=response}
    return response
end
local function tick()
    ticks=ticks+1
    local seq=read(base..'/request.ready')
    if not seq or seq==last_seq then return 'idle' end
    last_seq=seq
    local ok,response=pcall(function()
        assert(#seq<=32 and seq:match('^%d+$'),'invalid transport sequence')
        local payload=assert(read(base..'/request.json'),'request file missing')
        assert(#payload<=16384,'request too large')
        return execute(json.decode(payload))
    end)
    if not ok then response={ok=false,error=tostring(response),session=session,build=build} end
    write(base..'/response.json',json.encode(response))
    write(base..'/response.ready',seq)
    return 'ok'
end
_G.WB_Bridge={tick=function()
    local ok,r=pcall(tick)
    return ok and tostring(r) or ('bridge_tick_error: '..tostring(r))
end}
write(base..'/hello.json',json.encode({session=session,build=build,protocol=1,stage='ready',path_encoding=encoding,poll_ms=50,jass_globals=true,file_io=true}))
return {status='ready',tick=_G.WB_Bridge.tick}

-- Test-copy module. The JSON codec and transport are derived from the local
-- validated War3 test bridge; business actions are specific to this project.
local json=(function()
__JSON_CODEC__
end)()
local jass=require 'jass.common'
local g=require 'jass.globals'
local session=__SESSION__
local build=__BUILD__
local base=__IPC__
local function read(path)
    local f=io.open(path,'rb');if not f then return nil end
    local s=f:read('*a');f:close();return s
end
local function write(path,value)
    local f,e=io.open(path,'wb');assert(f,e);assert(f:write(value));assert(f:close())
end
assert(read(base..'/probe.txt')==session,'file_io_probe_failed')
local ticks,last_seq,cache=0,'',{}
local function snapshot()
    jass.ExecuteFunc('ZJB_Observe')
    local state=json.decode(g.ZJB_State)
    state.ticks=ticks
    state.last_error=g.ZJB_LastError
    return state
end
local function execute(req)
    assert(type(req)=='table','request must be object')
    assert(req.session==session,'wrong_session')
    assert(type(req.id)=='string' and #req.id>0 and #req.id<=80,'bad_request_id')
    assert(req.op=='ping' or req.op=='snapshot' or req.op=='activate' or req.op=='prepare','unknown_operation')
    local fingerprint=json.encode(req)
    local prior=cache[req.id]
    if prior then
        assert(prior.fingerprint==fingerprint,'request_id_conflict')
        return {ok=true,id=req.id,session=session,build=build,replayed=true,result=prior.result}
    end
    local dispatched=false
    if req.op=='activate' then
        assert(type(req.args)=='table','args must be object')
        local id=req.args.control
        assert(type(id)=='number' and id==math.floor(id) and id>=1 and id<=327,'bad_control')
        g.ZJB_Control=id
        jass.ExecuteFunc('ZJB_Activate')
        dispatched=g.ZJB_Accepted
    elseif req.op=='prepare' then
        assert(type(req.args)=='table','args must be object')
        local scenes={camp_trade=1,evolution_inheritance=2}
        assert(scenes[req.args.scene],'unknown_scene')
        assert(req.args.expected_serial==g.ZJB_SceneSerial,'stale_scene_serial')
        g.ZJB_Prepare=scenes[req.args.scene]
        jass.ExecuteFunc('ZJB_PrepareScene')
        dispatched=g.ZJB_Accepted
    end
    local result=snapshot()
    result.dispatched=dispatched
    cache[req.id]={fingerprint=fingerprint,result=result}
    return {ok=true,id=req.id,session=session,build=build,replayed=false,result=result}
end
local function tick()
    ticks=ticks+1
    local seq=read(base..'/request.ready')
    if not seq or seq==last_seq then return 'idle' end
    last_seq=seq
    local ok,response=pcall(function()
        assert(#seq<=32 and seq:match('^%d+$'),'invalid_transport_sequence')
        local payload=assert(read(base..'/request.json'),'request_file_missing')
        assert(#payload<=16384,'request_too_large')
        return execute(json.decode(payload))
    end)
    if not ok then response={ok=false,error=tostring(response),session=session,build=build} end
    write(base..'/response.json',json.encode(response))
    write(base..'/response.ready',seq)
    return 'ok'
end
_G.ZJB_Bridge={tick=function()
    local ok,value=pcall(tick)
    return ok and tostring(value) or ('bridge_tick_error: '..tostring(value))
end}
write(base..'/hello.json',json.encode({session=session,build=build,protocol=1,stage='ready',poll_ms=50,project='zhanjian',single_human_only=true}))
return {status='ready'}

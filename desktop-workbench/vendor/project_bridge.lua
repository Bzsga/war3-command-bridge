local json=(function()
__JSON_CODEC__
end)()
local jass=require 'jass.common'
local globals=require 'jass.globals'
local code=require 'jass.code'
local session=__SESSION__
local build=__BUILD__
local catalog=json.decode(__CATALOG__)
local base=__IPC__
local function read(path)local f=io.open(path,'rb');if not f then return nil end;local s=f:read('*a');f:close();return s end
local function write(path,s)local f=assert(io.open(path,'wb'));assert(f:write(s));assert(f:close()) end
assert(read(base..'/probe.txt')==session,'file communication probe failed')
local ticks,last_seq,cache=0,'',{}
local commands={}
for _,c in ipairs(catalog.commands) do commands[c.id]=c end
local function snapshot()
    local state={}
    for _,f in ipairs(catalog.fields) do
        local v
        if f.source=='ticks' then v=ticks
        elseif f.source=='gold' then v=jass.GetPlayerState(jass.Player(0),jass.PLAYER_STATE_RESOURCE_GOLD)
        elseif f.source=='lumber' then v=jass.GetPlayerState(jass.Player(0),jass.PLAYER_STATE_RESOURCE_LUMBER)
        elseif f.index~=nil then v=globals[f.name][f.index]
        else v=globals[f.name] end
        assert(v~=nil,'state field unavailable: '..f.id)
        state[f.id]=v
    end
    return state
end
local function scalar(v,kind)
    if kind=='integer' then assert(type(v)=='number' and v%1==0 and v>=-2147483648 and v<=2147483647,'integer parameter required')
    elseif kind=='real' then assert(type(v)=='number' and v==v and math.abs(v)<math.huge,'real parameter required')
    elseif kind=='boolean' then assert(type(v)=='boolean','boolean parameter required')
    else assert(type(v)=='string' and #v<=1024,'string parameter required') end
    return v
end
local function execute(req)
    assert(type(req)=='table' and req.session==session,'wrong_session')
    assert(type(req.id)=='string' and #req.id>0 and #req.id<=80,'bad_request_id')
    local fp=json.encode(req)
    if cache[req.id] then
        assert(cache[req.id].fp==fp,'request_id_conflict')
        local reply=cache[req.id].reply;reply.replayed=true;return reply
    end
    if req.op=='discover' then return {session=session,build=build,id=req.id,ok=true,result=catalog,replayed=false} end
    local command=commands[req.op]
    assert(command or req.op=='ping' or req.op=='snapshot','unknown_operation')
    local reply={session=session,build=build,id=req.id,ok=true,replayed=false}
    -- Reserve identity BEFORE calling business: a failure after mutation must not replay it.
    cache[req.id]={fp=fp,reply=reply}
    local ok,result=pcall(function()
        if command then
            local args=req.args or {};assert(type(args)=='table','args must be object')
            local ordered,allowed={},{}
            for i,p in ipairs(command.params or {}) do
                allowed[p.name]=true;local v=args[p.name];if v==nil then v=p.default end
                ordered[i]=scalar(v,p.type)
            end
            for name in pairs(args) do assert(allowed[name],'unknown parameter: '..name) end
            if command.entry_kind=='trigger' then
                local trg=globals[command.trigger];assert(trg~=nil and trg~=0,'trigger unavailable')
                assert(jass.IsTriggerEnabled(trg),'trigger disabled')
                reply.condition_passed=jass.TriggerEvaluate(trg)
                if reply.condition_passed then jass.TriggerExecute(trg) end
            else
                local fn=code[command['function']];assert(type(fn)=='function','business entry unavailable')
                fn((table.unpack or unpack)(ordered))
            end
        end
        return snapshot()
    end)
    if ok then reply.result=result;reply.dispatched=command~=nil
    else reply.ok=false;reply.error=tostring(result);reply.execution_may_have_occurred=command~=nil end
    return reply
end
local function tick()
    ticks=ticks+1
    local seq=read(base..'/request.ready')
    if not seq or seq==last_seq then return 'idle' end
    last_seq=seq
    local req
    local ok,reply=pcall(function()
        assert(#seq<=32 and seq:match('^%d+$'),'invalid transport sequence')
        local payload=assert(read(base..'/request.json'));assert(#payload<=16384,'request too large')
        req=json.decode(payload);return execute(req)
    end)
    if not ok then reply={ok=false,session=session,build=build,id=type(req)=='table' and req.id or nil,error=tostring(reply)} end
    local encoded,data=pcall(json.encode,reply)
    if not encoded then data=json.encode({ok=false,session=session,build=build,id=req and req.id,error='response_encode_failed',execution_may_have_occurred=true}) end
    write(base..'/response.json',data);write(base..'/response.ready',seq);return 'ok'
end
_G.WBT_Bridge={tick=tick}
write(base..'/hello.json',json.encode({session=session,build=build,stage='ready',protocol=1,poll_ms=50}))
return {status='ready'}

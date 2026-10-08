-- Test-copy module. The JSON codec and transport are derived from the local
-- validated War3 test bridge; business actions are specific to this project.
local json=(function()
__JSON_CODEC__
end)()
local jass=require 'jass.common'
local g=require 'jass.globals'
local code=require 'jass.code'
local session=__SESSION__
local build=__BUILD__
local base=__IPC__
local expected_humans=__HUMAN_LIMIT__
local seat=1
if expected_humans>1 then
    seat=jass.GetPlayerId(jass.GetLocalPlayer())+1
    base=base..'/seat-'..tostring(seat)
end
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
    -- Observations stay read-only and avoid nesting a new JASS ExecuteFunc
    -- thread in the Lua callback reached from the shared bridge timer.
    local p=seat
    local offset=(p-1)*128
    local details={unitHandle=jass.GetHandleId(g.U[p]),camp=g.MP_CampIndex[p],
        equipmentCount=g.MP_EquipCount[p],bondCount=g.MP_BondCount[p],evolutionCount=g.MP_EvolutionCount[p],
        burn=g.Burn[p],mark=g.Mark[p],coreCD=g.CoreCD[p],skillCD=g.CD[p*5+1],items=json.array({}),skills=json.array({}),shop=json.array({})}
    for i=0,5 do
        local item=jass.UnitItemInSlot(g.U[p],i)
        details.items[#details.items+1]={type=jass.GetItemTypeId(item),handle=jass.GetHandleId(item)}
    end
    for i=1,g.MP_GenericSkillCount[p] do details.skills[i]=g.GenericSkillPool[offset+i] end
    for i=1,8 do details.shop[i]={slot=i,goods=(g.ShopOptions[offset+i] or 0),price=(g.ShopPrice[offset+i] or 0),sold=(g.ShopSold[offset+i] or 0)} end
    local state={ready=g.ZJ_Ready,fault=g.RuntimeFault,singleHuman=g.MPCount==1,
        chapter=g.CurrentChapter,encounter=g.Encounter,eliteRound=g.CampaignEliteRound,running=g.Running,
        outcome=g.RunOutcome,page=g.UIPage,visible=g.UIVisible,localSeat=p,commandSequence=g.MPCommandSequence,
        normalClears=g.NormalClears,scene=g.ZJB_Scene,sceneSerial=g.ZJB_SceneSerial,details=details,
        ticks=ticks,last_error=g.ZJB_LastError,players=json.array({}),controls=json.array({})}
    for i=1,4 do
        state.players[i]={seat=i,active=g.MPActive[i],flow=g.MP_FlowState[i],speciesMode=g.MP_FlowSpeciesMode[i],
            speciesSerial=g.MP_FlowSpeciesSerial[i],rewardSerial=g.MP_FlowRewardSerial[i],gold=g.MP_RunGold[i],
            life=g.Life[i],kind=g.Kind[i],unitType=jass.GetUnitTypeId(g.U[i]),ready=g.MPReady[i],vote=g.MPVote[i]}
    end
    for id=1,327 do
        if g.UIEnabled[id] and ((g.UIVisible and g.UIOwnerPage[id]==g.UIPage) or (not g.UIVisible and id==75)) then
            state.controls[#state.controls+1]=id
        end
    end
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
        code.ZJB_Activate()
        dispatched=g.ZJB_Accepted
    elseif req.op=='prepare' then
        assert(type(req.args)=='table','args must be object')
        local scenes={camp_trade=1,evolution_inheritance=2}
        assert(scenes[req.args.scene],'unknown_scene')
        assert(req.args.expected_serial==g.ZJB_SceneSerial,'stale_scene_serial')
        g.ZJB_Prepare=scenes[req.args.scene]
        code.ZJB_PrepareScene()
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
    local encoded_ok,encoded=pcall(json.encode,response)
    if not encoded_ok then encoded=json.encode({ok=false,error='response_encoding_failed: '..tostring(encoded),id=response.id,session=session,build=build}) end
    write(base..'/response.json',encoded)
    write(base..'/response.ready',seq)
    return 'ok'
end
_G.ZJB_Bridge={tick=function()
    local ok,value=pcall(tick)
    return ok and tostring(value) or ('bridge_tick_error: '..tostring(value))
end}
write(base..'/hello.json',json.encode({session=session,build=build,protocol=1,stage='ready',poll_ms=50,project='zhanjian',single_human_only=expected_humans==1,expected_humans=expected_humans,localSeat=seat}))
return {status='ready'}

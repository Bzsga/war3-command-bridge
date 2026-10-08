-- Real Lua/file protocol, mocked game natives; does not attach to a game.
local module_path,base,codec_path,session=arg[1],arg[2],arg[3],arg[4]
local json=assert(loadfile(codec_path))()
local function write(path,value)
    local f=assert(io.open(path,'wb'));assert(f:write(value));assert(f:close())
end
local function read(path)
    local f=assert(io.open(path,'rb'));local value=f:read('*a');f:close();return value
end
local g={ZJB_State='{"ready":true}',ZJB_LastError='',ZJB_Accepted=false,ZJB_SceneSerial=0}
local function array(default)
    return setmetatable({},{__index=function() return default end})
end
g.ZJ_Ready=true;g.RuntimeFault=false;g.MPCount=1;g.CurrentChapter=1;g.Encounter=1;g.CampaignEliteRound=1
g.Running=false;g.RunOutcome=0;g.UIPage=1;g.UIVisible=true;g.MPCommandSequence=0;g.NormalClears=0;g.ZJB_Scene=0
g.U=array(0);g.MP_CampIndex=array(0);g.MP_EquipCount=array(0);g.MP_BondCount=array(0);g.MP_EvolutionCount=array(0)
g.Burn=array(0);g.Mark=array(0);g.CoreCD=array(0);g.CD=array(0);g.MP_GenericSkillCount=array(0);g.GenericSkillPool=array(0)
g.ShopOptions=array(0);g.ShopPrice=array(0);g.ShopSold=array(0);g.MPActive=array(false);g.MP_FlowState=array(0)
g.MP_FlowSpeciesMode=array(0);g.MP_FlowSpeciesSerial=array(0);g.MP_FlowRewardSerial=array(0);g.MP_RunGold=array(0)
g.Life=array(0);g.Kind=array(0);g.MPReady=array(false);g.MPVote=array(0);g.UIEnabled=array(false);g.UIOwnerPage=array(1)
g.MPActive[1]=true;g.UIEnabled[220]=true;g.U[1]=101;g.Life[1]=850;g.MP_RunGold[1]=50
g.MP_GenericSkillCount[1]=2;g.GenericSkillPool[1]=25;g.GenericSkillPool[2]=2
local actions=0
local preparations=0
package.loaded['jass.globals']=g
package.loaded['jass.common']={GetLocalPlayer=function() return 0 end,GetPlayerId=function(p) return p end,GetHandleId=function(h) return h or 0 end,UnitItemInSlot=function() return 0 end,GetItemTypeId=function() return 0 end,GetUnitTypeId=function(u) return u==101 and 1680879665 or 0 end,ExecuteFunc=function(name) error('nested JASS dispatch forbidden '..name) end}
package.loaded['jass.code']={ZJB_Activate=function() actions=actions+1;g.ZJB_Accepted=true end,
    ZJB_PrepareScene=function() preparations=preparations+1;g.ZJB_SceneSerial=g.ZJB_SceneSerial+1;g.ZJB_Accepted=true end}
write(base..'/probe.txt',session)
local source=read(module_path)
source=source:gsub('local base=[^\n]+',function() return 'local base='..string.format('%q',base) end,1)
local module=assert(load(source))()
assert(module.status=='ready','module bootstrap')
local seq,checks=0,{}
local function check(value,label)
    assert(value,label);checks[#checks+1]=label
end
local function exchange(req)
    seq=seq+1
    write(base..'/request.json',type(req)=='string' and req or json.encode(req))
    write(base..'/request.ready',tostring(seq))
    assert(ZJB_Bridge.tick()=='ok')
    assert(read(base..'/response.ready')==tostring(seq))
    return json.decode(read(base..'/response.json'))
end
local request={session=session,id='action-1',op='activate',args={control=220}}
local observed=exchange({session=session,id='ping-1',op='ping'})
check(observed.ok,'timer ping response')
check(observed.result.players[1].life==850 and observed.result.players[1].gold==50 and observed.result.players[1].unitType==1680879665,'read-only state mirrors formal globals and native unit')
check(#observed.result.details.items==6 and #observed.result.details.skills==2 and #observed.result.details.shop==8 and observed.result.controls[1]==220,'snapshot collections have correct array shape and contents')
check(exchange(request).result.dispatched and actions==1,'one fixed command dispatched')
check(exchange(request).replayed and actions==1,'duplicate request does not execute twice')
check(not exchange({session=session,id='action-1',op='activate',args={control=221}}).ok and actions==1,'conflicting ID rejected')
check(not exchange({session='old',id='old-1',op='activate',args={control=220}}).ok and actions==1,'stale session cannot mutate')
check(not exchange({session=session,id='bad-1',op='activate',args={control=328}}).ok and actions==1,'invalid control rejected')
check(not exchange({session=session,id='bad-2',op='execute-script'}).ok and actions==1,'arbitrary operations rejected')
check(not exchange('{broken json').ok,'malformed request returns error')
check(exchange({session=session,id='ping-2',op='ping'}).ok,'communication survives invalid requests')
local prep={session=session,id='prep-1',op='prepare',args={scene='camp_trade',expected_serial=0}}
check(exchange(prep).result.dispatched and preparations==1,'fixed scene dispatch')
check(exchange(prep).replayed and preparations==1,'scene replay does not prepare twice')
check(not exchange({session=session,id='prep-1',op='prepare',args={scene='evolution_inheritance',expected_serial=1}}).ok,'scene ID conflict rejected')
check(not exchange({session=session,id='prep-stale',op='prepare',args={scene='evolution_inheritance',expected_serial=0}}).ok,'stale scene serial rejected')
check(not exchange({session=session,id='prep-unknown',op='prepare',args={scene='arbitrary',expected_serial=1}}).ok,'unknown scene rejected')
check(exchange({session=session,id='prep-2',op='prepare',args={scene='evolution_inheritance',expected_serial=1}}).result.dispatched and preparations==2,'second fixed scene dispatch after errors')
g.UIPage=function() end
local bad=exchange({session=session,id='encoding-bad',op='snapshot'})
check(not bad.ok and bad.id=='encoding-bad' and bad.error:find('response_encoding_failed',1,true),'response encoding error preserves identity and returns explicit receipt')
g.UIPage=1
check(exchange({session=session,id='encoding-recovery',op='snapshot'}).ok,'protocol recovers after response encoding failure')
write(base..'/check.json',json.encode({passed=true,checks=json.array(checks),boundary='Real Lua and file exchange with mocked JASS; no live-game proof'}))
print('PASS transport: '..#checks..' checks')

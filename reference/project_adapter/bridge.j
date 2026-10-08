// Test-copy only. Commands enter the existing local UI -> sync receiver path.
function ZJB_Mark takes string stage, string message returns nothing
    call PreloadGenClear()
    call PreloadGenStart()
    call Preload(message)
    call PreloadGenEnd("Logs\\ZJB-__BUILD_TEXT__-"+stage+".pld")
endfunction
function ZJB_Bool takes boolean value returns string
    if value then
        return "true"
    endif
    return "false"
endfunction

function ZJB_Details takes nothing returns nothing
    local integer p=GetPlayerId(GetLocalPlayer())+1
    local integer i=0
    local integer offset=(p-1)*128
    local string items=""
    local string skills=""
    local string shop=""
    loop
        exitwhen i>=6
        if i>0 then
            set items=items+","
        endif
        set items=items+"{\"type\":"+I2S(GetItemTypeId(UnitItemInSlot(U[p],i)))+",\"handle\":"+I2S(GetHandleId(UnitItemInSlot(U[p],i)))+"}"
        set i=i+1
    endloop
    set i=1
    loop
        exitwhen i>MP_GenericSkillCount[p]
        if i>1 then
            set skills=skills+","
        endif
        set skills=skills+I2S(GenericSkillPool[offset+i])
        set i=i+1
    endloop
    set i=1
    loop
        exitwhen i>8
        if i>1 then
            set shop=shop+","
        endif
        set shop=shop+"{\"slot\":"+I2S(i)+",\"goods\":"+I2S(ShopOptions[offset+i])+",\"price\":"+I2S(ShopPrice[offset+i])+",\"sold\":"+I2S(ShopSold[offset+i])+"}"
        set i=i+1
    endloop
    set ZJB_Detail="{\"unitHandle\":"+I2S(GetHandleId(U[p]))+",\"camp\":"+I2S(MP_CampIndex[p])+",\"equipmentCount\":"+I2S(MP_EquipCount[p])+",\"bondCount\":"+I2S(MP_BondCount[p])+",\"evolutionCount\":"+I2S(MP_EvolutionCount[p])+",\"burn\":"+I2S(Burn[p])+",\"mark\":"+I2S(Mark[p])+",\"coreCD\":"+R2S(CoreCD[p])+",\"skillCD\":"+R2S(CD[p*5+1])+",\"items\":["+items+"],\"skills\":["+skills+"],\"shop\":["+shop+"]}"
endfunction

function ZJB_Observe takes nothing returns nothing
    local integer p=1
    local integer id=1
    local string players=""
    local string controls=""
    loop
        exitwhen p>4
        if p>1 then
            set players=players+"," 
        endif
        set players=players+"{\"seat\":"+I2S(p)+",\"active\":"+ZJB_Bool(MPActive[p])+",\"flow\":"+I2S(MP_FlowState[p])+",\"speciesMode\":"+I2S(MP_FlowSpeciesMode[p])+",\"speciesSerial\":"+I2S(MP_FlowSpeciesSerial[p])+",\"rewardSerial\":"+I2S(MP_FlowRewardSerial[p])+",\"gold\":"+I2S(MP_RunGold[p])+",\"life\":"+I2S(Life[p])+",\"kind\":"+I2S(Kind[p])+",\"unitType\":"+I2S(GetUnitTypeId(U[p]))+",\"ready\":"+ZJB_Bool(MPReady[p])+",\"vote\":"+I2S(MPVote[p])+"}"
        set p=p+1
    endloop
    loop
        exitwhen id>327
        if UIEnabled[id] and ((UIVisible and UIOwnerPage[id]==UIPage) or (not UIVisible and id==75)) then
            if controls!="" then
                set controls=controls+","
            endif
            set controls=controls+I2S(id)
        endif
        set id=id+1
    endloop
    set ZJB_State="{\"ready\":"+ZJB_Bool(ZJ_Ready)+",\"fault\":"+ZJB_Bool(RuntimeFault)+",\"singleHuman\":"+ZJB_Bool(MPCount==1)+",\"chapter\":"+I2S(CurrentChapter)+",\"encounter\":"+I2S(Encounter)+",\"eliteRound\":"+I2S(CampaignEliteRound)+",\"running\":"+ZJB_Bool(Running)+",\"outcome\":"+I2S(RunOutcome)+",\"page\":"+I2S(UIPage)+",\"visible\":"+ZJB_Bool(UIVisible)+",\"localSeat\":"+I2S(GetPlayerId(GetLocalPlayer())+1)+",\"commandSequence\":"+I2S(MPCommandSequence)+",\"players\":["+players+"],\"controls\":["+controls+"]}"
    set ZJB_State="{\"normalClears\":"+I2S(NormalClears)+","+SubString(ZJB_State,1,StringLength(ZJB_State))
    call ZJB_Details()
    set ZJB_State="{\"scene\":"+I2S(ZJB_Scene)+",\"sceneSerial\":"+I2S(ZJB_SceneSerial)+",\"details\":"+ZJB_Detail+","+SubString(ZJB_State,1,StringLength(ZJB_State))
endfunction

function ZJB_PrepareScene takes nothing returns nothing
    local integer old=MPContext
    local integer p=GetPlayerId(GetLocalPlayer())+1
    set ZJB_Accepted=false
    if not ZJ_Ready or RuntimeFault or MPCount!=1 or Running or p<1 or p>4 or not MPActive[p] then
        return
    endif
    set MPContext=p
    if ZJB_Prepare==1 and ZJB_Scene==0 and MP_FlowState[p]==3 and MP_CampIndex[p]==1 and NormalClears==1 then
        // Fixed test precondition only; the purchase uses formal UI/sync logic.
        call FlowSideChoice(1)
        call FlowEnterCamp()
        call EnterCamp(2)
        call SetRunGold(500)
        set ZJB_Scene=1
        set ZJB_Accepted=true
    elseif ZJB_Prepare==2 and ZJB_Scene==1 and MP_FlowState[p]==3 and MP_CampIndex[p]==2 and MP_EquipCount[p]>0 and MP_EvolutionCount[p]==0 then
        // Reuse the normal second-camp -> evolution transition.
        call FlowSideChoice(1)
        call FlowEnterCamp()
        if MP_FlowState[p]==4 and not RuntimeFault then
            call SetUnitState(U[p],UNIT_STATE_LIFE,210.0)
            call ReadCombatant(p)
            set Burn[p]=2
            set Mark[p]=3
            set CoreCD[p]=4
            set CD[p*5+1]=2
            set ZJB_Scene=2
            set ZJB_Accepted=true
        endif
    endif
    if ZJB_Accepted then
        set ZJB_SceneSerial=ZJB_SceneSerial+1
        if GetLocalPlayer()==Player(p-1) then
            set UIPendingReward=0
            set UIPage=1
            call UIShow(true)
            call UIRefresh()
        endif
    endif
    set MPContext=old
endfunction

function ZJB_Activate takes nothing returns nothing
    local integer old=MPContext
    local integer p=GetPlayerId(GetLocalPlayer())+1
    local integer id=ZJB_Control
    set ZJB_Accepted=false
    if not ZJ_Ready or RuntimeFault or MPCount<1 or MPCount>ZJB_HumanLimit or p<1 or p>4 or not MPActive[p] then
        return
    endif
    if id<1 or id>327 or not UIEnabled[id] then
        return
    endif
    if not ((UIVisible and UIOwnerPage[id]==UIPage) or (not UIVisible and id==75)) then
        return
    endif
    set MPContext=p
    call UIActivate(id)
    set MPContext=old
    // Dispatch is acknowledged here; synchronized settlement may arrive later.
    set ZJB_Accepted=true
endfunction

function ZJB_Tick takes nothing returns nothing
    set ZJB_LastError=EXExecuteScript("ZJB_Bridge.tick()")
endfunction

function ZJB_Init takes nothing returns nothing
    local timer clock=GetExpiredTimer()
    if not ZJ_Ready and not RuntimeFault then
        return
    endif
    call PauseTimer(clock)
    call DestroyTimer(clock)
    set clock=null
    if RuntimeFault or MPCount!=ZJB_HumanLimit then
        call ZJB_Mark("blocked","fault="+ZJB_Bool(RuntimeFault)+" players="+I2S(MPCount))
        return
    endif
    call ZJB_Mark("ready","project ready; loading Lua module")
    call Cheat("exec-lua:ZJCommandBridge")
    set ZJB_LastError=EXExecuteScript("(require'ZJCommandBridge').status")
    call ZJB_Mark("module",ZJB_LastError)
    if ZJB_LastError=="ready" then
        set ZJB_Timer=CreateTimer()
        call TimerStart(ZJB_Timer,0.05,true,function ZJB_Tick)
    endif
endfunction

function ZJB_Start takes nothing returns nothing
    call ZJB_Mark("start","project bootstrap returned; bridge timer scheduled")
    call TimerStart(CreateTimer(),0.10,true,function ZJB_Init)
endfunction

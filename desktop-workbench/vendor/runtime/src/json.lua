-- Small data-only JSON codec. No load/loadstring or executable input.
local J = {}
local null = {}; J.null = null
local array_mt = {}; J.array = function(t) return setmetatable(t or {},array_mt) end
local function utf8(n)
    if n < 128 then return string.char(n) end
    if n < 2048 then return string.char(192 + math.floor(n/64),128+n%64) end
    if n < 65536 then return string.char(224+math.floor(n/4096),128+math.floor(n/64)%64,128+n%64) end
    return string.char(240+math.floor(n/262144),128+math.floor(n/4096)%64,128+math.floor(n/64)%64,128+n%64)
end
function J.decode(s)
    local i, depth = 1, 0
    local function ws() while s:sub(i,i):match('[ \r\n\t]') do i=i+1 end end
    local value
    local function str()
        assert(s:sub(i,i)=='"','expected string'); i=i+1
        local out={}
        while i<=#s do
            local c=s:sub(i,i); i=i+1
            if c=='"' then return table.concat(out) end
            if c=='\\' then
                local e=s:sub(i,i); i=i+1
                local esc={['"']='"',['\\']='\\',['/']='/',b='\b',f='\f',n='\n',r='\r',t='\t'}
                if e=='u' then
                    local h=s:sub(i,i+3); assert(h:match('^%x%x%x%x$'),'bad unicode escape'); i=i+4
                    local n=tonumber(h,16)
                    if n>=55296 and n<=56319 then
                        assert(s:sub(i,i+1)=='\\u','missing low surrogate');i=i+2
                        local h2=s:sub(i,i+3);assert(h2:match('^%x%x%x%x$'),'bad low surrogate');i=i+4
                        local n2=tonumber(h2,16);assert(n2>=56320 and n2<=57343,'bad low surrogate')
                        n=65536+(n-55296)*1024+n2-56320
                    else assert(n<56320 or n>57343,'unexpected low surrogate') end
                    out[#out+1]=utf8(n)
                else assert(esc[e],'bad escape');out[#out+1]=esc[e] end
            else assert(c:byte()>=32,'control character in string');out[#out+1]=c end
        end
        error('unterminated string')
    end
    function value()
        ws();depth=depth+1;assert(depth<=16,'JSON too deep')
        local c=s:sub(i,i);local result
        if c=='"' then result=str()
        elseif c=='{' or c=='[' then
            local object=c=='{';local stop=object and '}' or ']';i=i+1;ws();result=object and {} or J.array()
            if s:sub(i,i)~=stop then
                while true do
                    local key
                    if object then key=str();ws();assert(s:sub(i,i)==':','missing colon');i=i+1 end
                    local v=value()
                    if object then assert(result[key]==nil,'duplicate key');result[key]=v else result[#result+1]=v end
                    ws();local nextc=s:sub(i,i)
                    if nextc==stop then break end
                    assert(nextc==',','missing comma');i=i+1;ws()
                end
            end
            assert(s:sub(i,i)==stop,'missing close');i=i+1
        elseif s:sub(i,i+3)=='true' then result=true;i=i+4
        elseif s:sub(i,i+4)=='false' then result=false;i=i+5
        elseif s:sub(i,i+3)=='null' then result=null;i=i+4
        else
            local token=s:sub(i):match('^%-?%d+%.?%d*[eE]?[%+%-]?%d*')
            assert(token and #token>0,'invalid value')
            assert(not token:match('^%-?0%d'),'leading zero')
            assert(not token:match('%.([^%d])') and not token:match('%.$'),'missing fraction')
            result=tonumber(token);assert(result and result==result and math.abs(result)<math.huge,'bad number');i=i+#token
        end
        depth=depth-1;return result
    end
    local result=value();ws();assert(i>#s,'trailing input');return result
end
local function quote(s)
    return '"'..s:gsub('[%z\1-\31\\"]',function(c)
        local m={['"']='\\"',['\\']='\\\\',['\n']='\\n',['\r']='\\r',['\t']='\\t'}
        return m[c] or string.format('\\u%04x',c:byte())
    end)..'"'
end
function J.encode(v)
    local t=type(v)
    if v==null or t=='nil' then return 'null' end
    if t=='string' then return quote(v) end
    if t=='boolean' then return v and 'true' or 'false' end
    if t=='number' then assert(v==v and math.abs(v)<math.huge,'nonfinite');return string.format('%.17g',v) end
    assert(t=='table','unsupported JSON type')
    local out={}
    if getmetatable(v)==array_mt then
        for i,x in ipairs(v) do out[i]=J.encode(x) end
        return '['..table.concat(out,',')..']'
    end
    for k,x in pairs(v) do assert(type(k)=='string','object keys must be strings');out[#out+1]=quote(k)..':'..J.encode(x) end
    table.sort(out);return '{'..table.concat(out,',')..'}'
end
return J
